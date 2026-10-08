"""Alert configs: where a monitor's open/resolve notifications go."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alerts.dispatch import send
from ..auth import (
    SANDBOX_LIMITS,
    Principal,
    assert_public_url,
    editable_monitor,
    editor,
)
from ..db import get_session
from ..models import AlertChannel, AlertConfig, Incident, Monitor
from ..schemas import AlertConfigCreate, AlertConfigOut

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/monitors/{monitor_id}/alerts", response_model=list[AlertConfigOut])
async def list_alerts(
    monitor_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
) -> list[AlertConfig]:
    """Alert destinations are private (email addresses), so editors only."""
    await editable_monitor(session, monitor_id, p)
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
    p: Principal = Depends(editor),
) -> AlertConfig:
    await editable_monitor(session, monitor_id, p)
    dest = payload.destination.strip()
    if p.role == "sandbox":
        if payload.channel == AlertChannel.email:
            raise HTTPException(422, "sandbox alerts are webhook-only")
        used = await session.scalar(
            select(func.count())
            .select_from(AlertConfig)
            .join(Monitor, Monitor.id == AlertConfig.monitor_id)
            .where(Monitor.user_id == p.user_id)
        )
        if used >= SANDBOX_LIMITS["webhooks"]:
            raise HTTPException(429, f"sandbox limit: {SANDBOX_LIMITS['webhooks']} webhooks")
    if payload.channel == AlertChannel.email and "@" not in dest:
        raise HTTPException(422, "destination must be an email address")
    if payload.channel == AlertChannel.webhook and not dest.startswith(("http://", "https://")):
        raise HTTPException(422, "destination must be an http(s) URL")
    if payload.channel == AlertChannel.webhook:
        await assert_public_url(dest)
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
async def delete_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
) -> None:
    config = await session.get(AlertConfig, alert_id)
    if config is None:
        return
    await editable_monitor(session, config.monitor_id, p)
    await session.execute(delete(AlertConfig).where(AlertConfig.id == alert_id))
    await session.commit()


@router.post("/alerts/{alert_id}/test")
async def test_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
) -> dict:
    """Send a sample notification through one config. Not recorded in sent_alerts."""
    config = await session.get(AlertConfig, alert_id)
    if config is None:
        raise HTTPException(404, "alert not found")
    monitor = await editable_monitor(session, config.monitor_id, p)
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
