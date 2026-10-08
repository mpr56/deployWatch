"""APScheduler wiring: decides *when* checks run. engine.py decides *how*.

Key idea -- one job per interval bucket, not one job per monitor.

A thousand monitors on 60s intervals is one job that fires every 60 seconds and
checks a thousand URLs, not a thousand jobs. Jobs are the expensive thing;
concurrent HTTP requests are cheap and already bounded by the engine's
semaphore.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text

from ..db import SessionLocal
from ..models import Monitor
from .engine import run_due_checks

log = logging.getLogger("deploywatch.scheduler")

# The interval values monitors are allowed to use. Constraining to a handful of
# buckets is what keeps the job count constant as monitors grow.
INTERVAL_BUCKETS = [30, 60, 300, 900, 3600]

_scheduler: AsyncIOScheduler | None = None


def start() -> AsyncIOScheduler:
    """Create the scheduler and register one job per bucket.

    Returns the scheduler so main.py can shut it down cleanly.
    """
    global _scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")

    for bucket in INTERVAL_BUCKETS:
        scheduler.add_job(
            _run_bucket,
            "interval",
            seconds=bucket,
            args=[bucket],
            id=f"checks-{bucket}s",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(bucket // 2, 1),
        )

    scheduler.add_job(
        _ensure_partition,
        "interval",
        days=1,
        id="ensure-partition",
        max_instances=1,
        coalesce=True,
    )

    # v3: nightly uptime rollup (and a 90-day backfill on boot), SSL expiry
    # twice a day (and once shortly after boot).
    from datetime import datetime, timedelta, timezone

    from ..jobs import rollup, ssl_check

    soon = datetime.now(timezone.utc) + timedelta(seconds=20)
    scheduler.add_job(rollup.rollup, "cron", hour=0, minute=10, args=[2],
                      id="rollup-nightly", max_instances=1, coalesce=True)
    scheduler.add_job(rollup.rollup, "date", run_date=soon, args=[90], id="rollup-backfill")
    scheduler.add_job(ssl_check.check_all, "interval", hours=12, next_run_time=soon,
                      id="ssl-check", max_instances=1, coalesce=True)

    scheduler.start()
    _scheduler = scheduler
    return scheduler


async def _run_bucket(bucket: int) -> None:
    async with SessionLocal() as session:
        ids = list(
            await session.scalars(
                select(Monitor.id).where(
                    Monitor.is_active.is_(True), Monitor.interval_secs == bucket
                )
            )
        )
    if not ids:
        return
    try:
        written = await run_due_checks(ids)
        log.info("bucket %ss: %d checks written", bucket, written)
    except Exception:
        log.exception("bucket %ss: batch failed", bucket)


async def _ensure_partition() -> None:
    async with SessionLocal() as session:
        await session.execute(text("SELECT ensure_checks_partition(now()::date)"))
        await session.commit()


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
