"""Incident list and detail.

Plumbing only. Nothing lands in this table until checker/detector.py exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Check, Incident
from ..schemas import CheckOut, IncidentOut

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    monitor_id: int | None = None,
    open_only: bool = False,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[Incident]:
    stmt = select(Incident).order_by(Incident.started_at.desc()).limit(limit)
    if monitor_id is not None:
        stmt = stmt.where(Incident.monitor_id == monitor_id)
    if open_only:
        stmt = stmt.where(Incident.resolved_at.is_(None))
    return list(await session.scalars(stmt))


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: int, session: AsyncSession = Depends(get_session)
) -> Incident:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    return incident


@router.get("/{incident_id}/checks", response_model=list[CheckOut])
async def incident_checks(
    incident_id: int, session: AsyncSession = Depends(get_session)
) -> list[Check]:
    """Every check from the first failure to recovery (or now, if still open).

    Includes the passing checks during a flap, so the timeline shows
    down -> recovering -> down rather than hiding the noise.
    """
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
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
