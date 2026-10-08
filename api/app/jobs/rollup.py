"""Daily uptime rollup: checks -> daily_uptime, one row per (monitor, UTC day).

Only completed days are rolled up; "today" is always computed live from checks
(one day of rows, cheap). The nightly job re-rolls the last couple of days so a
late write is never lost; startup backfills the last 90 so a fresh deploy has
history immediately.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger("deploywatch.rollup")

ROLLUP_SQL = text("""
    INSERT INTO daily_uptime (monitor_id, day, total, up, degraded, down, avg_ms)
    SELECT monitor_id,
           (checked_at AT TIME ZONE 'UTC')::date AS day,
           count(*),
           count(*) FILTER (WHERE status = 'up'),
           count(*) FILTER (WHERE status = 'degraded'),
           count(*) FILTER (WHERE status = 'down'),
           round(avg(response_time_ms))::int
    FROM checks
    WHERE checked_at >= (date_trunc('day', now() AT TIME ZONE 'UTC') - make_interval(days => :days)) AT TIME ZONE 'UTC'
      AND checked_at <  date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
    GROUP BY 1, 2
    ON CONFLICT (monitor_id, day) DO UPDATE SET
        total = EXCLUDED.total, up = EXCLUDED.up, degraded = EXCLUDED.degraded,
        down = EXCLUDED.down, avg_ms = EXCLUDED.avg_ms
""")


async def rollup(days: int = 2) -> None:
    async with SessionLocal() as session:
        result = await session.execute(ROLLUP_SQL, {"days": days})
        await session.commit()
    log.info("rolled up %s monitor-days (last %s days)", result.rowcount, days)
