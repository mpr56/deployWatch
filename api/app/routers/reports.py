"""Monthly SLA report: per-monitor uptime, downtime and incidents for one month."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/monthly")
async def monthly_report(
    month: str = Query(pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    sla: float = Query(default=99.9, gt=0, le=100),
    session: AsyncSession = Depends(get_session),
):
    year, mon = map(int, month.split("-"))
    if not 1 <= mon <= 12:
        raise HTTPException(422, "month must be YYYY-MM")
    start = date(year, mon, 1)
    end = date(year, mon, calendar.monthrange(year, mon)[1])  # inclusive
    today = datetime.now(timezone.utc).date()

    # Rolled-up days, plus today live if today falls inside the month.
    rows = await session.execute(
        text("""
            WITH days AS (
                SELECT monitor_id, total, down, avg_ms FROM daily_uptime
                WHERE day BETWEEN :start AND :end AND day < :today
                UNION ALL
                SELECT monitor_id, count(*), count(*) FILTER (WHERE status = 'down'),
                       round(avg(response_time_ms))::int
                FROM checks
                WHERE :today BETWEEN :start AND :end
                  AND checked_at >= (:today)::timestamp AT TIME ZONE 'UTC'
                GROUP BY monitor_id
            ),
            agg AS (
                SELECT monitor_id, sum(total) AS total, sum(down) AS down,
                       round(sum(avg_ms * total)::numeric / NULLIF(sum(total) FILTER (WHERE avg_ms IS NOT NULL), 0)) AS avg_ms
                FROM days GROUP BY monitor_id
            ),
            inc AS (
                SELECT monitor_id,
                       count(*) FILTER (WHERE started_at >= (:start)::timestamp AT TIME ZONE 'UTC') AS incidents,
                       sum(EXTRACT(EPOCH FROM
                           LEAST(coalesce(resolved_at, now()), ((:end)::timestamp + INTERVAL '1 day') AT TIME ZONE 'UTC')
                         - GREATEST(started_at, (:start)::timestamp AT TIME ZONE 'UTC')))::int AS downtime_secs
                FROM incidents
                WHERE started_at < ((:end)::timestamp + INTERVAL '1 day') AT TIME ZONE 'UTC'
                  AND coalesce(resolved_at, now()) > (:start)::timestamp AT TIME ZONE 'UTC'
                GROUP BY monitor_id
            )
            SELECT m.id, m.name, m.url, m.ssl_expires_at,
                   coalesce(a.total, 0) AS checks, coalesce(a.down, 0) AS failed, a.avg_ms,
                   coalesce(i.incidents, 0) AS incidents, coalesce(i.downtime_secs, 0) AS downtime_secs
            FROM monitors m
            LEFT JOIN agg a ON a.monitor_id = m.id
            LEFT JOIN inc i ON i.monitor_id = m.id
            ORDER BY m.name
        """),
        {"start": start, "end": end, "today": today},
    )

    monitors = []
    for r in rows:
        uptime = round(100 * (r.checks - r.failed) / r.checks, 3) if r.checks else None
        monitors.append(
            {
                "id": r.id,
                "name": r.name,
                "url": r.url,
                "checks": r.checks,
                "failed_checks": r.failed,
                "uptime_pct": uptime,
                "sla_met": None if uptime is None else uptime >= sla,
                "incidents": r.incidents,
                "downtime_secs": r.downtime_secs,
                "avg_ms": int(r.avg_ms) if r.avg_ms is not None else None,
                "ssl_expires_at": r.ssl_expires_at,
            }
        )
    return {"month": month, "sla_target": sla, "monitors": monitors}
