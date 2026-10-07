"""APScheduler wiring: decides *when* checks run. engine.py decides *how*.

Key idea -- one job per interval bucket, not one job per monitor.

A thousand monitors on 60s intervals is one job that fires every 60 seconds and
checks a thousand URLs, not a thousand jobs. Jobs are the expensive thing;
concurrent HTTP requests are cheap and already bounded by the engine's
semaphore.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# The interval values monitors are allowed to use. Constraining to a handful of
# buckets is what keeps the job count constant as monitors grow.
INTERVAL_BUCKETS = [30, 60, 300, 900, 3600]

_scheduler: AsyncIOScheduler | None = None


def start() -> AsyncIOScheduler:
    """Create the scheduler and register one job per bucket.

    TODO (you):
      - `AsyncIOScheduler()`, then for each bucket in INTERVAL_BUCKETS add an
        interval job calling a coroutine that (a) selects active monitors with
        that interval_secs and (b) hands the ids to engine.run_due_checks.
      - Pass `max_instances=1` and `coalesce=True` per job. Without those, a
        batch that overruns its interval stacks up behind itself and you get a
        thundering herd against your own monitored services.
      - `misfire_grace_time` of about half the interval -- after a pause, run
        once, do not replay every missed firing.
      - Call ensure_checks_partition(now()) on a daily job. Writing into a
        month with no partition fails the INSERT, and it fails at midnight on
        the 1st, which is a bad time to find out.

    Returns the scheduler so main.py can shut it down cleanly.
    """
    raise NotImplementedError("app/checker/scheduler.py:start")


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
