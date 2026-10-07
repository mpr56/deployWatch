"""Check history: raw log, time series, percentiles.

`list_checks` is written for you as a reference. The two below it are yours --
they are the queries worth writing by hand, and both are v2 work.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import CheckOut, CheckStats

router = APIRouter(prefix="/api/checks", tags=["checks"])

Range = Literal["1h", "24h", "7d", "30d"]

# Range -> (postgres interval, bucket width for the chart). Keeping the mapping
# in one place means the frontend only ever sends "24h" and never an interval.
RANGES: dict[str, tuple[str, str]] = {
    "1h": ("1 hour", "1 minute"),
    "24h": ("24 hours", "10 minutes"),
    "7d": ("7 days", "1 hour"),
    "30d": ("30 days", "6 hours"),
}


def _interval(range_: str) -> str:
    if range_ not in RANGES:
        raise HTTPException(400, f"range must be one of {list(RANGES)}")
    return RANGES[range_][0]


@router.get("", response_model=list[CheckOut])
async def list_checks(
    monitor_id: int,
    range: Range = "24h",
    limit: int = Query(default=200, le=2000),
    session: AsyncSession = Depends(get_session),
) -> list[CheckOut]:
    """Raw checks, newest first. Feeds the dense table on the monitor detail screen.

    Always bounded by both a time window and a limit -- an unbounded query
    against this table is how you take the page down.
    """
    rows = await session.execute(
        text(f"""
            SELECT id, monitor_id, status, response_time_ms, status_code,
                   error_message, checked_at
            FROM checks
            WHERE monitor_id = :monitor_id
              AND checked_at >= now() - INTERVAL '{_interval(range)}'
            ORDER BY checked_at DESC
            LIMIT :limit
        """),
        {"monitor_id": monitor_id, "limit": limit},
    )
    return [CheckOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/series")
async def check_series(
    monitor_id: int,
    range: Range = "24h",
    session: AsyncSession = Depends(get_session),
):
    """Bucketed response times for the big chart.

    TODO (you): return one row per time bucket:
        {bucket, avg_ms, p95_ms, total, failed}

    Hints:
      - `date_bin(INTERVAL '10 minutes', checked_at, TIMESTAMPTZ '2000-01-01')`
        gives you fixed-width buckets. Bucket width per range is in RANGES.
      - Plot avg and p95 as two lines; p95 is where the interesting spikes live.
      - Empty buckets do not appear in the result. Decide whether the chart
        shows a gap or interpolates -- a gap is more honest and it is the
        picture of an outage.
    """
    raise HTTPException(501, "not built yet -- app/routers/checks.py:check_series")


@router.get("/stats", response_model=CheckStats)
async def check_stats(
    monitor_id: int,
    range: Range = "24h",
    session: AsyncSession = Depends(get_session),
) -> CheckStats:
    """P50/P95/P99 + uptime for the stat row above the chart.

    TODO (you): one query, one round trip.

    Hints:
      - `percentile_cont(0.95) WITHIN GROUP (ORDER BY response_time_ms)` --
        it is an ordered-set aggregate, so it goes in the SELECT list like
        count() and you can compute all three plus uptime at once.
      - Exclude NULL response times (failed requests never got a timing) or
        your percentiles quietly describe a different population than you think.
    """
    raise HTTPException(501, "not built yet -- app/routers/checks.py:check_stats")
