"""Incident list and detail.

Plumbing only. Nothing lands in this table until checker/detector.py exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Incident
from ..schemas import IncidentOut

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


# TODO (you, v2): GET /api/incidents/{id}/checks
# The failing checks between started_at and resolved_at -- that is the timeline
# on the incident detail screen. One bounded range query over `checks`.
