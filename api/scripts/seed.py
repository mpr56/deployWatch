"""Seed realistic check history so the UI has something to render before the
checker exists.

Deliberately includes a monitor that is down right now and one that is degraded
right now. Design the down state first -- it is easy to make an all-green
dashboard look great and discover it falls apart the moment something breaks.

    python -m scripts.seed          # wipes and reseeds
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import insert, text  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.models import Check, CheckStatus, Incident, Monitor  # noqa: E402

random.seed(7)  # same fixtures every run, so screenshots stay comparable

HOURS = 24
INTERVAL = 60

MONITORS = [
    # (name, url, base_ms, jitter_ms, profile)
    ("Dashboard", "https://dash-simple.vercel.app", 180, 60, "healthy"),
    ("API gateway", "https://api.example.com/health", 240, 90, "down_now"),
    ("Checkout service", "https://checkout.example.com/ping", 1400, 500, "degraded_now"),
    ("Docs", "https://docs.example.com", 120, 40, "past_incident"),
]


def timings(profile: str, base: int, jitter: int, i: int, total: int):
    """Return (status_code, response_time_ms, error) for check #i of `total`.

    i == 0 is the oldest check, i == total-1 is the newest.
    """
    from_end = total - 1 - i

    if profile == "down_now" and from_end < 18:
        return None, None, "Connection refused"
    if profile == "past_incident" and 400 < from_end < 460:
        return 503, 90, "HTTP 503 Service Unavailable"
    if profile == "healthy" and random.random() < 0.004:
        return None, None, "Read timeout"
    # Keep the degraded monitor reliably over the 1000ms line for the last
    # half hour. Left to the Gaussian it drifts back under and the fixture
    # stops demonstrating the state it exists to demonstrate.
    if profile == "degraded_now" and from_end < 30:
        return 200, random.randint(1300, 2600), None

    ms = max(20, int(random.gauss(base, jitter)))
    # Occasional latency spike, because real traffic has them and the chart
    # should have something to show.
    if random.random() < 0.02:
        ms *= random.randint(3, 8)
    return 200, ms, None


async def main() -> None:
    now = datetime.now(UTC)
    total = HOURS * 3600 // INTERVAL

    async with SessionLocal() as session:
        await session.execute(
            text("SELECT ensure_checks_partition((now() - INTERVAL '1 month')::date)")
        )
        await session.execute(text("SELECT ensure_checks_partition(now()::date)"))
        # TRUNCATE ... CASCADE clears checks and incidents via the FK.
        await session.execute(text("TRUNCATE monitors CASCADE"))
        await session.commit()

        for name, url, base, jitter, profile in MONITORS:
            monitor = Monitor(
                name=name,
                url=url,
                interval_secs=INTERVAL,
                degraded_ms=1000,
                timeout_ms=10_000,
            )
            session.add(monitor)
            await session.flush()

            rows = []
            for i in range(total):
                at = now - timedelta(seconds=(total - 1 - i) * INTERVAL)
                code, ms, err = timings(profile, base, jitter, i, total)
                if code is None or code != 200:
                    status = CheckStatus.down
                elif ms >= 1000:
                    status = CheckStatus.degraded
                else:
                    status = CheckStatus.up
                rows.append(
                    {
                        "monitor_id": monitor.id,
                        "status": status,
                        "response_time_ms": ms,
                        "status_code": code,
                        "error_message": err,
                        "checked_at": at,
                    }
                )

            # One statement, not `total` statements.
            await session.execute(insert(Check), rows)

            if profile == "down_now":
                session.add(
                    Incident(
                        monitor_id=monitor.id,
                        started_at=now - timedelta(seconds=18 * INTERVAL),
                        cause="Connection refused",
                        checks_failed=18,
                    )
                )
            elif profile == "past_incident":
                started = now - timedelta(seconds=459 * INTERVAL)
                resolved = now - timedelta(seconds=401 * INTERVAL)
                session.add(
                    Incident(
                        monitor_id=monitor.id,
                        started_at=started,
                        resolved_at=resolved,
                        duration_secs=int((resolved - started).total_seconds()),
                        cause="HTTP 503 Service Unavailable",
                        checks_failed=58,
                    )
                )

            await session.commit()
            print(f"  {name}: {len(rows)} checks")

    await engine.dispose()
    print(f"\nSeeded {len(MONITORS)} monitors x {total} checks.")
    print("API gateway is DOWN and Checkout is DEGRADED -- design those first.")


if __name__ == "__main__":
    asyncio.run(main())
