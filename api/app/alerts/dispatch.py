"""Alert delivery: email (SMTP) and webhook (POST).

Called by detector.py on state transitions only -- open and resolve.

A failing alert channel must never break the checker: every send is wrapped,
logged, and skipped. Delivery is at-most-once per (incident, config, event),
recorded in sent_alerts before sending so a retry cannot page twice.
"""

from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..config import get_settings
from ..db import SessionLocal
from ..models import AlertChannel, AlertConfig, Incident, Monitor, SentAlert

log = logging.getLogger("deploywatch.alerts")


async def dispatch(monitor: Monitor, incident: Incident, event: str) -> None:
    """Send every active alert config for this monitor. `event` is "opened" | "resolved"."""
    async with SessionLocal() as session:
        configs = list(
            await session.scalars(
                select(AlertConfig).where(
                    AlertConfig.monitor_id == monitor.id,
                    AlertConfig.is_active.is_(True),
                )
            )
        )
        to_send: list[AlertConfig] = []
        for config in configs:
            claimed = await session.scalar(
                pg_insert(SentAlert)
                .values(incident_id=incident.id, alert_config_id=config.id, event=event)
                .on_conflict_do_nothing()
                .returning(SentAlert.id)
            )
            if claimed is not None:
                to_send.append(config)
        await session.commit()

    results = await asyncio.gather(
        *(send(c, monitor, incident, event) for c in to_send), return_exceptions=True
    )
    for config, result in zip(to_send, results):
        if isinstance(result, Exception):
            log.warning(
                "alert %s (%s -> %s) failed: %s",
                config.id, config.channel.value, config.destination, result,
            )


async def send(config: AlertConfig, monitor: Monitor, incident: Incident, event: str) -> None:
    if config.channel == AlertChannel.email:
        await _send_email(config.destination, monitor, incident, event)
    else:
        await _send_webhook(config.destination, monitor, incident, event)


def _summary(monitor: Monitor, incident: Incident, event: str) -> tuple[str, str]:
    if event == "opened":
        subject = f"[DeployWatch] {monitor.name} is DOWN"
        body = (
            f"{monitor.name} ({monitor.url}) is down.\n\n"
            f"Started: {incident.started_at:%Y-%m-%d %H:%M:%S %Z}\n"
            f"Cause: {incident.cause or 'unknown'}\n"
            f"Failed checks so far: {incident.checks_failed}\n"
        )
    elif event == "resolved":
        mins, secs = divmod(incident.duration_secs or 0, 60)
        subject = f"[DeployWatch] {monitor.name} recovered"
        body = (
            f"{monitor.name} ({monitor.url}) is back up.\n\n"
            f"Down for: {mins}m {secs}s\n"
            f"Failed checks: {incident.checks_failed}\n"
            f"Cause: {incident.cause or 'unknown'}\n"
        )
    else:  # "test"
        subject = f"[DeployWatch] Test alert for {monitor.name}"
        body = f"This is a test alert for {monitor.name} ({monitor.url}). Delivery works.\n"
    return subject, body


async def _send_email(to: str, monitor: Monitor, incident: Incident, event: str) -> None:
    settings = get_settings()
    subject, body = _summary(monitor, incident, event)
    msg = EmailMessage()
    msg["From"] = settings.alert_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_starttls,
        timeout=10,
    )


async def _send_webhook(url: str, monitor: Monitor, incident: Incident, event: str) -> None:
    subject, _ = _summary(monitor, incident, event)
    payload = {
        "event": event,
        "text": subject,
        "monitor": {"id": monitor.id, "name": monitor.name, "url": monitor.url},
        "incident": {
            "id": incident.id,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "duration_secs": incident.duration_secs,
            "cause": incident.cause,
            "checks_failed": incident.checks_failed,
        },
    }
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
