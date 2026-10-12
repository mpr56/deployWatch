"""Nightly data retention.

- `checks` (partitioned monthly): drop a whole monthly partition once the
  entire month is older than RETENTION_CHECKS_DAYS. A DROP TABLE, not a
  DELETE, so no heap bloat. A partition is only dropped if every
  (monitor, day) it holds already has a daily_uptime row; otherwise it is
  skipped with a warning, because that raw data is the only copy.
- `daily_uptime`: rows older than RETENTION_ROLLUP_DAYS.
- `sent_alerts`: rows older than RETENTION_ALERTS_DAYS.

Incidents are kept: they are small and worth having forever.
Set RETENTION_DRY_RUN=true to log what would go without deleting anything.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from ..config import get_settings
from ..db import SessionLocal

log = logging.getLogger("deploywatch.retention")

PARTITION_RE = re.compile(r"^checks_(\d{4})_(\d{2})$")

LIST_PARTITIONS_SQL = text("""
    SELECT c.relname
    FROM pg_inherits i
    JOIN pg_class c ON c.oid = i.inhrelid
    WHERE i.inhparent = 'checks'::regclass
""")


def _month_end(start: date) -> date:
    return date(start.year + start.month // 12, start.month % 12 + 1, 1)


def expired_partitions(names: list[str], cutoff: date) -> list[str]:
    """Partitions whose whole month ends on or before `cutoff`, oldest first."""
    out = []
    for name in sorted(names):
        m = PARTITION_RE.match(name)
        if m and _month_end(date(int(m[1]), int(m[2]), 1)) <= cutoff:
            out.append(name)
    return out


async def prune(dry_run: bool | None = None) -> None:
    settings = get_settings()
    dry_run = settings.retention_dry_run if dry_run is None else dry_run
    verb = "would " if dry_run else ""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=settings.retention_checks_days)).date()

    async with SessionLocal() as session:
        names = list(await session.scalars(LIST_PARTITIONS_SQL))
        for name in expired_partitions(names, cutoff):
            # `name` matched PARTITION_RE, so it is safe to interpolate.
            gap = await session.scalar(text(f"""
                SELECT 1
                FROM (SELECT DISTINCT monitor_id,
                             (checked_at AT TIME ZONE 'UTC')::date AS day
                      FROM {name}) c
                LEFT JOIN daily_uptime u
                       ON u.monitor_id = c.monitor_id AND u.day = c.day
                WHERE u.monitor_id IS NULL
                LIMIT 1
            """))
            if gap:
                log.warning("not dropping %s: some days have no daily_uptime rollup", name)
                continue
            log.info("%sdrop partition %s", verb, name)
            if not dry_run:
                await session.execute(text(f"DROP TABLE {name}"))
                await session.commit()

        rollup_cutoff = (now - timedelta(days=settings.retention_rollup_days)).date()
        alerts_cutoff = now - timedelta(days=settings.retention_alerts_days)
        if dry_run:
            n_rollup = await session.scalar(
                text("SELECT count(*) FROM daily_uptime WHERE day < :c"), {"c": rollup_cutoff})
            n_alerts = await session.scalar(
                text("SELECT count(*) FROM sent_alerts WHERE sent_at < :c"), {"c": alerts_cutoff})
        else:
            n_rollup = (await session.execute(
                text("DELETE FROM daily_uptime WHERE day < :c"), {"c": rollup_cutoff})).rowcount
            n_alerts = (await session.execute(
                text("DELETE FROM sent_alerts WHERE sent_at < :c"), {"c": alerts_cutoff})).rowcount
            await session.commit()
    log.info("%sdelete %s daily_uptime row(s), %s sent_alerts row(s)", verb, n_rollup, n_alerts)
