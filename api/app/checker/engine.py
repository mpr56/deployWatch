"""The checker. One async loop, bounded concurrency, no threads.

500 monitors must be the same process shape as 5: one event loop, gather over
a semaphore, one shared httpx.AsyncClient so connections get reused.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import insert, select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Check, CheckStatus, Monitor

log = logging.getLogger("deploywatch.checker")


@dataclass(slots=True)
class CheckResult:
    status: CheckStatus
    status_code: int | None = None
    response_time_ms: int | None = None
    error_message: str | None = None


def classify(
    status_code: int | None,
    elapsed_ms: int | None,
    expected_status: int,
    degraded_ms: int,
) -> CheckStatus:
    """Three states, not two.

    down     -- no response at all, or the wrong status code
    degraded -- right status code, but slower than the monitor's threshold
    up       -- right status code, fast enough

    A site returning 200s in 3 seconds is technically fine and practically
    broken. That case is the entire reason `degraded` exists, and it is the
    state people forget to design for.
    """
    if status_code is None or status_code != expected_status:
        return CheckStatus.down
    if elapsed_ms is not None and elapsed_ms >= degraded_ms:
        return CheckStatus.degraded
    return CheckStatus.up


async def run_check(
    url: str,
    timeout_ms: int,
    expected_status: int,
    degraded_ms: int,
    client=None,
) -> CheckResult:
    """Perform exactly one HTTP check. Never raises -- a failure IS the result.

    A timeout is `down` with response_time_ms=None, not the timeout value.
    client=None makes a throwaway client (the "Test now" path).
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient()

    started = time.perf_counter()
    try:
        resp = await client.get(
            url, timeout=timeout_ms / 1000, follow_redirects=True
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CheckResult(
            status=classify(resp.status_code, elapsed_ms, expected_status, degraded_ms),
            status_code=resp.status_code,
            response_time_ms=elapsed_ms,
            error_message=(
                None
                if resp.status_code == expected_status
                else f"expected {expected_status}, got {resp.status_code}"
            ),
        )
    except httpx.TimeoutException:
        return CheckResult(
            status=CheckStatus.down,
            error_message=f"timed out after {timeout_ms / 1000:g}s",
        )
    except httpx.ConnectError as exc:
        return CheckResult(
            status=CheckStatus.down, error_message=_connect_message(exc)
        )
    except httpx.RequestError as exc:
        return CheckResult(
            status=CheckStatus.down,
            error_message=str(exc) or type(exc).__name__,
        )
    except Exception as exc:  # run_check never raises
        return CheckResult(
            status=CheckStatus.down,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if own_client:
            await client.aclose()


def _connect_message(exc: httpx.ConnectError) -> str:
    text = str(exc).lower()
    if "refused" in text or "all connection attempts failed" in text:
        return "connection refused"
    if "name or service not known" in text or "nodename nor servname" in text:
        return "DNS lookup failed"
    if "ssl" in text or "certificate" in text:
        return "TLS error"
    return str(exc) or "connection failed"


async def run_due_checks(monitor_ids: list[int]) -> int:
    """Check a batch of monitors concurrently and persist the results.

    Returns how many checks were written.
    """
    if not monitor_ids:
        return 0

    async with SessionLocal() as session:
        monitors = (
            await session.scalars(
                select(Monitor).where(
                    Monitor.id.in_(monitor_ids), Monitor.is_active.is_(True)
                )
            )
        ).all()
        if not monitors:
            return 0

        sem = asyncio.Semaphore(get_settings().checker_concurrency)

        async with httpx.AsyncClient() as client:

            async def one(m: Monitor) -> tuple[Monitor, CheckResult]:
                async with sem:
                    result = await run_check(
                        m.url,
                        m.timeout_ms,
                        m.expected_status,
                        m.degraded_ms,
                        client=client,
                    )
                return m, result

            results = await asyncio.gather(*(one(m) for m in monitors))

        await session.execute(
            insert(Check),
            [
                {
                    "monitor_id": m.id,
                    "status": r.status,
                    "response_time_ms": r.response_time_ms,
                    "status_code": r.status_code,
                    "error_message": r.error_message,
                }
                for m, r in results
            ],
        )
        await session.commit()

    # v2: detector.evaluate(m, r) for each (m, r) goes here, after the commit.
    return len(results)
