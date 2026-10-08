"""Alert configs: where a monitor's open/resolve notifications go."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alerts.dispatch import send
from ..db import get_session
from ..models import AlertChannel, AlertConfig, Incident, Monitor
from ..schemas import AlertConfigCreate, AlertConfigOut

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/monitors/{monitor_id}/alerts", response_model=list[AlertConfigOut])
async def list_alerts(
    monitor_id: int, session: AsyncSession = Depends(get_session)
) -> list[AlertConfig]:
    return list(
        await session.scalars(
            select(AlertConfig)
            .where(AlertConfig.monitor_id == monitor_id)
            .order_by(AlertConfig.id)
        )
    )


@router.post(
    "/monitors/{monitor_id}/alerts",
    response_model=AlertConfigOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert(
    monitor_id: int,
    payload: AlertConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertConfig:
    if await session.get(Monitor, monitor_id) is None:
        raise HTTPException(404, "monitor not found")
    dest = payload.destination.strip()
    if payload.channel == AlertChannel.email and "@" not in dest:
        raise HTTPException(422, "destination must be an email address")
    if payload.channel == AlertChannel.webhook and not dest.startswith(("http://", "https://")):
        raise HTTPException(422, "destination must be an http(s) URL")
    config = AlertConfig(
        monitor_id=monitor_id,
        channel=payload.channel,
        destination=dest,
        is_active=payload.is_active,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: int, session: AsyncSession = Depends(get_session)) -> None:
    await session.execute(delete(AlertConfig).where(AlertConfig.id == alert_id))
    await session.commit()


@router.post("/alerts/{alert_id}/test")
async def test_alert(alert_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    """Send a sample notification through one config. Not recorded in sent_alerts."""
    config = await session.get(AlertConfig, alert_id)
    if config is None:
        raise HTTPException(404, "alert not found")
    monitor = await session.get(Monitor, config.monitor_id)
    sample = Incident(
        id=0,
        monitor_id=monitor.id,
        started_at=datetime.now(timezone.utc),
        cause="test alert",
        checks_failed=0,
    )
    try:
        await send(config, monitor, sample, "test")
    except Exception as exc:
        raise HTTPException(502, f"delivery failed: {exc}") from exc
    return {"ok": True}
