"""Incident list and detail.

Plumbing only. Nothing lands in this table until checker/detector.py exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal, principal, visible_monitor, visible_user_ids
from ..db import get_session
from ..models import Check, Incident, Monitor
from ..schemas import CheckOut, IncidentOut

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    monitor_id: int | None = None,
    open_only: bool = False,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(principal),
) -> list[Incident]:
    stmt = (
        select(Incident)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .where(Monitor.user_id.in_(visible_user_ids(p)))
        .order_by(Incident.started_at.desc())
        .limit(limit)
    )
    if monitor_id is not None:
        stmt = stmt.where(Incident.monitor_id == monitor_id)
    if open_only:
        stmt = stmt.where(Incident.resolved_at.is_(None))
    return list(await session.scalars(stmt))


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(principal),
) -> Incident:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    await visible_monitor(session, incident.monitor_id, p)
    return incident


@router.get("/{incident_id}/checks", response_model=list[CheckOut])
async def incident_checks(
    incident_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(principal),
) -> list[Check]:
    """Every check from the first failure to recovery (or now, if still open).

    Includes the passing checks during a flap, so the timeline shows
    down -> recovering -> down rather than hiding the noise.
    """
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    await visible_monitor(session, incident.monitor_id, p)
    end = incident.resolved_at or func.now()
    return list(
        await session.scalars(
            select(Check)
            .where(
                Check.monitor_id == incident.monitor_id,
                Check.checked_at >= incident.started_at,
                Check.checked_at <= end,
            )
            .order_by(Check.checked_at.asc())
            .limit(1000)
        )
    )
