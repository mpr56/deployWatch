"""Check history: raw log, time series, percentiles.

`list_checks` is written for you as a reference. The two below it are yours --
they are the queries worth writing by hand, and both are v2 work.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal, principal, visible_monitor
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
    p: Principal = Depends(principal),
) -> list[CheckOut]:
    """Raw checks, newest first. Feeds the dense table on the monitor detail screen.

    Always bounded by both a time window and a limit -- an unbounded query
    against this table is how you take the page down.
    """
    await visible_monitor(session, monitor_id, p)
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
    p: Principal = Depends(principal),
):
    """Bucketed response times for the big chart.

    One row per bucket across the whole window. Buckets with no checks, or
    where every check failed (no timings), come back with null avg/p95 so the
    chart shows a gap -- the picture of an outage -- instead of interpolating.
    """
    await visible_monitor(session, monitor_id, p)
    _interval(range)  # validates range
    interval, width = RANGES[range]
    rows = await session.execute(
        text(f"""
            WITH buckets AS (
                SELECT generate_series(
                    date_bin(INTERVAL '{width}',
                             now() - INTERVAL '{interval}',
                             TIMESTAMPTZ '2000-01-01'),
                    now(),
                    INTERVAL '{width}'
                ) AS bucket
            ),
            agg AS (
                SELECT date_bin(INTERVAL '{width}', checked_at,
                                TIMESTAMPTZ '2000-01-01') AS bucket,
                       avg(response_time_ms) AS avg_ms,
                       percentile_cont(0.95) WITHIN GROUP
                           (ORDER BY response_time_ms) AS p95_ms,
                       count(*) AS total,
                       count(*) FILTER (WHERE status = 'down') AS failed
                FROM checks
                WHERE monitor_id = :monitor_id
                  AND checked_at >= now() - INTERVAL '{interval}'
                GROUP BY 1
            )
            SELECT b.bucket,
                   round(a.avg_ms)::int  AS avg_ms,
                   round(a.p95_ms)::int  AS p95_ms,
                   coalesce(a.total, 0)  AS total,
                   coalesce(a.failed, 0) AS failed
            FROM buckets b
            LEFT JOIN agg a USING (bucket)
            ORDER BY b.bucket
        """),
        {"monitor_id": monitor_id},
    )
    return [
        {
            "bucket": r.bucket,
            "avg_ms": r.avg_ms,
            "p95_ms": r.p95_ms,
            "total": r.total,
            "failed": r.failed,
        }
        for r in rows
    ]


@router.get("/stats", response_model=CheckStats)
async def check_stats(
    monitor_id: int,
    range: Range = "24h",
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(principal),
) -> CheckStats:
    """P50/P95/P99 + uptime for the stat row above the chart.

    Percentiles ignore failed requests (NULL timing). Uptime counts degraded as
    available, matching the dashboard's 24h figure.
    """
    await visible_monitor(session, monitor_id, p)
    row = (
        await session.execute(
            text(f"""
                SELECT count(*) AS count,
                       percentile_cont(0.50) WITHIN GROUP
                           (ORDER BY response_time_ms) AS p50,
                       percentile_cont(0.95) WITHIN GROUP
                           (ORDER BY response_time_ms) AS p95,
                       percentile_cont(0.99) WITHIN GROUP
                           (ORDER BY response_time_ms) AS p99,
                       100.0 * count(*) FILTER (WHERE status <> 'down')
                           / NULLIF(count(*), 0) AS uptime_pct
                FROM checks
                WHERE monitor_id = :monitor_id
                  AND checked_at >= now() - INTERVAL '{_interval(range)}'
            """),
            {"monitor_id": monitor_id},
        )
    ).one()
    return CheckStats(
        count=row.count,
        p50_ms=row.p50,
        p95_ms=row.p95,
        p99_ms=row.p99,
        uptime_pct=row.uptime_pct,
    )
