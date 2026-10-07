"""Monitor CRUD + the dashboard summary.

This is the reference router -- the query patterns here (bounded time windows,
one round trip per screen, no N+1) are what checks.py and incidents.py should
copy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import CheckStatus, Monitor
from ..schemas import (
    MonitorCreate,
    MonitorOut,
    MonitorSummary,
    MonitorUpdate,
    TestCheckResult,
)

router = APIRouter(prefix="/api/monitors", tags=["monitors"])

SPARKLINE_POINTS = 30


async def _get_or_404(session: AsyncSession, monitor_id: int) -> Monitor:
    monitor = await session.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "monitor not found")
    return monitor


@router.get("", response_model=list[MonitorSummary])
async def list_monitors(
    session: AsyncSession = Depends(get_session),
) -> list[MonitorSummary]:
    """Everything the dashboard needs, in three queries regardless of monitor count.

    Deliberately not one clever query -- three obvious ones are easier to read
    and the planner handles each well. All of them are bounded by
    checks_monitor_time_idx and the current month's partition.
    """
    monitors = (await session.scalars(select(Monitor).order_by(Monitor.id))).all()
    if not monitors:
        return []

    ids = [m.id for m in monitors]

    # 1. Rolling 24h uptime. "Up" counts degraded as available -- a slow site is
    #    still serving. If you'd rather degraded not count, change it here and
    #    nowhere else.
    agg_rows = await session.execute(
        text("""
            SELECT monitor_id,
                   count(*)                                              AS total,
                   count(*) FILTER (WHERE status <> 'down')              AS ok
            FROM checks
            WHERE monitor_id = ANY(:ids)
              AND checked_at >= now() - INTERVAL '24 hours'
            GROUP BY monitor_id
        """),
        {"ids": ids},
    )
    uptime = {
        r.monitor_id: (r.ok / r.total * 100.0) if r.total else None
        for r in agg_rows
    }

    # 2. The last N checks per monitor, for the sparkline. ROW_NUMBER over a
    #    partition is the standard "top N per group" shape.
    spark_rows = await session.execute(
        text(f"""
            SELECT monitor_id, status, response_time_ms, status_code, checked_at, rn
            FROM (
                SELECT monitor_id, status, response_time_ms, status_code, checked_at,
                       row_number() OVER (
                           PARTITION BY monitor_id ORDER BY checked_at DESC
                       ) AS rn
                FROM checks
                WHERE monitor_id = ANY(:ids)
                  AND checked_at >= now() - INTERVAL '24 hours'
            ) ranked
            WHERE rn <= {SPARKLINE_POINTS}
            ORDER BY monitor_id, checked_at ASC
        """),
        {"ids": ids},
    )

    # Raw SQL hands back plain strings; the schema is typed with the enum.
    # Coerce here rather than letting Pydantic do it on the way out -- direct
    # attribute assignment below skips validation.
    spark: dict[int, list[CheckStatus]] = {}
    latest: dict[int, tuple] = {}
    for r in spark_rows:
        status = CheckStatus(r.status)
        spark.setdefault(r.monitor_id, []).append(status)
        if r.rn == 1:
            latest[r.monitor_id] = (status, r.response_time_ms, r.checked_at)

    out = []
    for m in monitors:
        last = latest.get(m.id)
        summary = MonitorSummary.model_validate(m)
        summary.uptime_24h = uptime.get(m.id)
        summary.sparkline = spark.get(m.id, [])
        if last:
            summary.current_status, summary.last_response_time_ms, summary.last_checked_at = last
        out.append(summary)
    return out


@router.post("", response_model=MonitorOut, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    payload: MonitorCreate, session: AsyncSession = Depends(get_session)
) -> Monitor:
    monitor = Monitor(**payload.model_dump(mode="json"))
    session.add(monitor)
    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.get("/{monitor_id}", response_model=MonitorOut)
async def get_monitor(
    monitor_id: int, session: AsyncSession = Depends(get_session)
) -> Monitor:
    return await _get_or_404(session, monitor_id)


@router.patch("/{monitor_id}", response_model=MonitorOut)
async def update_monitor(
    monitor_id: int,
    payload: MonitorUpdate,
    session: AsyncSession = Depends(get_session),
) -> Monitor:
    monitor = await _get_or_404(session, monitor_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(monitor, field, value)
    await session.commit()
    await session.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    await _get_or_404(session, monitor_id)
    # ON DELETE CASCADE takes the checks and incidents with it.
    await session.execute(delete(Monitor).where(Monitor.id == monitor_id))
    await session.commit()


@router.post("/test", response_model=TestCheckResult)
async def test_monitor(payload: MonitorCreate) -> TestCheckResult:
    """The "Test now" button. Runs one check, writes nothing, returns the result.

    Needs checker.engine.run_check -- see api/app/checker/engine.py.
    """
    from ..checker.engine import run_check

    result = await run_check(
        url=str(payload.url),
        timeout_ms=payload.timeout_ms,
        expected_status=payload.expected_status,
        degraded_ms=payload.degraded_ms,
    )
    return TestCheckResult(**result.__dict__)
