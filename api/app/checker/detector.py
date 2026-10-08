"""Incident state machine.  up -> down -> recovering -> up

A single failed check is not an incident, and a single successful check is not
a recovery. Both transitions need consecutive confirmation, with deliberately
different thresholds (settings.incident_open_after / incident_close_after).

    up          N consecutive failures      -> open incident
    down        1 success                   -> recovering (incident stays open)
    recovering  M consecutive successes     -> close incident
    recovering  1 failure                   -> back to down, same incident

State is derived from the checks table rather than kept in memory, so it is
correct across restarts. "Recovering" is never stored: it is simply an open
incident whose latest checks are passing but not yet M of them.

Only `down` counts as a failure. Degraded is slow-but-serving, same as uptime.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..alerts.dispatch import dispatch
from ..config import get_settings
from ..db import SessionLocal
from ..models import Check, CheckStatus, Incident, Monitor

log = logging.getLogger("deploywatch.detector")

DOWN = CheckStatus.down


async def evaluate(monitor_id: int, result_status: CheckStatus) -> None:
    """Fold the latest (already committed) check into the incident state."""
    settings = get_settings()
    event: str | None = None

    async with SessionLocal() as session:
        incident = await session.scalar(
            select(Incident).where(
                Incident.monitor_id == monitor_id, Incident.resolved_at.is_(None)
            )
        )

        if incident is None:
            if result_status != DOWN:
                return
            incident = await _maybe_open(session, monitor_id, settings.incident_open_after)
            if incident is None:
                return
            event = "opened"

        elif result_status == DOWN:
            # Still down, or a recovery that did not hold: same incident.
            await session.execute(
                update(Incident)
                .where(Incident.id == incident.id)
                .values(checks_failed=Incident.checks_failed + 1)
            )
            await session.commit()
            return

        else:
            if not await _maybe_close(session, incident, settings.incident_close_after):
                return
            event = "resolved"

        monitor = await session.get(Monitor, monitor_id)

    log.info("monitor %s: incident %s %s", monitor_id, incident.id, event)
    if monitor is not None:
        try:
            await dispatch(monitor, incident, event)
        except Exception:
            log.exception("alert dispatch failed for incident %s", incident.id)


async def _recent_statuses(session, monitor_id: int, n: int) -> list[CheckStatus]:
    rows = await session.scalars(
        select(Check.status)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc())
        .limit(n)
    )
    return list(rows)


async def _maybe_open(session, monitor_id: int, n: int) -> Incident | None:
    recent = await _recent_statuses(session, monitor_id, n)
    if len(recent) < n or any(s != DOWN for s in recent):
        return None

    # The outage began at the first failure of the current run, not when we
    # noticed on the Nth check.
    last_ok: datetime | None = await session.scalar(
        select(func.max(Check.checked_at)).where(
            Check.monitor_id == monitor_id, Check.status != DOWN
        )
    )
    run = select(Check).where(Check.monitor_id == monitor_id, Check.status == DOWN)
    if last_ok is not None:
        run = run.where(Check.checked_at > last_ok)
    first = await session.scalar(run.order_by(Check.checked_at.asc()).limit(1))
    failed = await session.scalar(
        select(func.count()).select_from(run.subquery())
    )

    incident = Incident(
        monitor_id=monitor_id,
        started_at=first.checked_at,
        cause=first.error_message,
        checks_failed=failed or n,
    )
    session.add(incident)
    try:
        await session.commit()
    except IntegrityError:
        # incidents_one_open_per_monitor: another evaluation got there first.
        await session.rollback()
        return None
    await session.refresh(incident)
    return incident


async def _maybe_close(session, incident: Incident, m: int) -> bool:
    recent = await _recent_statuses(session, incident.monitor_id, m)
    if len(recent) < m or any(s == DOWN for s in recent):
        return False

    in_incident = (Check.monitor_id == incident.monitor_id) & (
        Check.checked_at >= incident.started_at
    )
    last_fail = await session.scalar(
        select(func.max(Check.checked_at)).where(in_incident, Check.status == DOWN)
    )
    recovered_at = await session.scalar(
        select(func.min(Check.checked_at)).where(
            in_incident,
            Check.status != DOWN,
            Check.checked_at > (last_fail or incident.started_at),
        )
    )
    failed = await session.scalar(
        select(func.count()).where(in_incident, Check.status == DOWN)
    )

    incident.resolved_at = recovered_at
    incident.duration_secs = int((recovered_at - incident.started_at).total_seconds())
    incident.checks_failed = failed or incident.checks_failed
    await session.commit()
    return True
