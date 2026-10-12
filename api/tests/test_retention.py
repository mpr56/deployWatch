"""Run against a scratch database (never the dev one):

    TEST_DATABASE_URL=postgresql+psycopg://deploywatch:deploywatch@localhost:5433/retention_test \
        ../.venv/bin/python -m pytest tests
"""

import asyncio
import os
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.jobs import retention

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


def test_expired_partitions_pure():
    names = ["checks_2026_01", "checks_2026_02", "checks_2026_09", "checks_2026_10", "other"]
    # Cutoff Oct 5: Sep ends Oct 1 (<= cutoff, expired); Oct ends Nov 1 (kept).
    assert retention.expired_partitions(names, date(2026, 10, 5)) == [
        "checks_2026_01", "checks_2026_02", "checks_2026_09"]
    # December rolls the year correctly.
    assert retention.expired_partitions(["checks_2026_12"], date(2027, 1, 1)) == ["checks_2026_12"]
    assert retention.expired_partitions(["checks_2026_12"], date(2026, 12, 31)) == []


@pytest.fixture
def db(monkeypatch):
    engine = create_async_engine(URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(retention, "SessionLocal", maker)
    get_settings.cache_clear()
    monkeypatch.setenv("RETENTION_DRY_RUN", "false")

    async def reset():
        async with maker() as s:
            for part in await s.scalars(retention.LIST_PARTITIONS_SQL):
                await s.execute(text(f"DROP TABLE {part}"))
            await s.execute(text("TRUNCATE monitors RESTART IDENTITY CASCADE"))
            await s.commit()

    asyncio.run(reset())
    yield maker
    get_settings.cache_clear()
    asyncio.run(engine.dispose())


def _month_start(d: datetime, back: int) -> date:
    y, m = d.year, d.month - back
    while m < 1:
        y, m = y - 1, m + 12
    return date(y, m, 1)


async def _seed(maker, rolled_up_old: bool):
    now = datetime.now(timezone.utc)
    old, recent = _month_start(now, 4), _month_start(now, 0)
    async with maker() as s:
        await s.execute(text("INSERT INTO monitors (name, url) VALUES ('m', 'http://x')"))
        for d in (old, recent):
            await s.execute(text("SELECT ensure_checks_partition(:d)"), {"d": d})
            await s.execute(text(
                "INSERT INTO checks (monitor_id, status, checked_at) VALUES (1, 'up', :t)"),
                {"t": datetime(d.year, d.month, 2, 12, tzinfo=timezone.utc)})
        if rolled_up_old:
            await s.execute(text(
                "INSERT INTO daily_uptime VALUES (1, :d, 1, 1, 0, 0, 5)"),
                {"d": date(old.year, old.month, 2)})
        # rollup/alert rows on both sides of their cutoffs
        for days in (500, 10):
            await s.execute(text("INSERT INTO daily_uptime VALUES (1, :d, 1, 1, 0, 0, 5)"),
                            {"d": (now - timedelta(days=days)).date()})
        await s.execute(text(
            "INSERT INTO incidents (monitor_id, started_at) VALUES (1, now() - interval '200 days')"))
        await s.execute(text("INSERT INTO alert_configs (monitor_id, channel, destination) "
                             "VALUES (1, 'email', 'a@b.c')"))
        for i, days in enumerate((120, 5)):
            await s.execute(text(
                "INSERT INTO sent_alerts (incident_id, alert_config_id, event, sent_at) "
                "VALUES (1, 1, :e, now() - make_interval(days => :d))"),
                {"e": ("opened", "resolved")[i], "d": days})
        await s.commit()
        return old, recent


async def _state(maker):
    async with maker() as s:
        parts = sorted(await s.scalars(retention.LIST_PARTITIONS_SQL))
        rollups = await s.scalar(text("SELECT count(*) FROM daily_uptime"))
        alerts = await s.scalar(text("SELECT count(*) FROM sent_alerts"))
        incidents = await s.scalar(text("SELECT count(*) FROM incidents"))
        return parts, rollups, alerts, incidents


def test_prunes_old_and_keeps_recent(db):
    old, recent = asyncio.run(_seed(db, rolled_up_old=True))
    asyncio.run(retention.prune())
    parts, rollups, alerts, incidents = asyncio.run(_state(db))
    assert parts == [f"checks_{recent:%Y_%m}"]
    assert rollups == 2  # 500d row gone; ~120d (rolled-up month) and 10d rows kept
    assert alerts == 1
    assert incidents == 1  # incidents are never pruned


def test_skips_partition_without_rollup(db):
    old, recent = asyncio.run(_seed(db, rolled_up_old=False))
    asyncio.run(retention.prune())
    parts, *_ = asyncio.run(_state(db))
    assert parts == sorted([f"checks_{old:%Y_%m}", f"checks_{recent:%Y_%m}"])


def test_dry_run_deletes_nothing(db):
    old, recent = asyncio.run(_seed(db, rolled_up_old=True))
    before = asyncio.run(_state(db))
    asyncio.run(retention.prune(dry_run=True))
    assert asyncio.run(_state(db)) == before
