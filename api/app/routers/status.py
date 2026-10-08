"""Public status page API. No auth, cacheable, deliberately minimal.

Whatever this returns is public: display names and states only. No URLs, no
error messages, no latency numbers.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Monitor, StatusPage, StatusPageMonitor

router = APIRouter(prefix="/api/status", tags=["status"])

DAYS = 90
SEVERITY = {"up": 0, "degraded": 1, "down": 2}


def _day_state(total: int, down: int) -> str:
    """Colour of one day's bar. A single failed check in 1,440 is not a red day."""
    if total == 0:
        return "none"
    if down == 0:
        return "up"
    return "partial" if (total - down) / total >= 0.99 else "down"


@router.get("/{slug}")
async def public_status(
    slug: str, response: Response, session: AsyncSession = Depends(get_session)
):
    page = await session.scalar(select(StatusPage).where(StatusPage.slug == slug))
    if page is None:
        raise HTTPException(404, "status page not found")

    monitors = list(
        await session.scalars(
            select(Monitor)
            .join(StatusPageMonitor, StatusPageMonitor.monitor_id == Monitor.id)
            .where(StatusPageMonitor.status_page_id == page.id)
            .order_by(StatusPageMonitor.position, Monitor.name)
        )
    )
    ids = [m.id for m in monitors] or [-1]
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=DAYS - 1)

    # Completed days from the rollup, today live from checks (one day of rows).
    rows = await session.execute(
        text("""
            SELECT monitor_id, day, total, down FROM daily_uptime
            WHERE monitor_id = ANY(:ids) AND day >= :first AND day < :today
            UNION ALL
            SELECT monitor_id, :today AS day, count(*), count(*) FILTER (WHERE status = 'down')
            FROM checks
            WHERE monitor_id = ANY(:ids)
              AND checked_at >= (:today)::timestamp AT TIME ZONE 'UTC'
            GROUP BY monitor_id
        """),
        {"ids": ids, "first": first_day, "today": today},
    )
    days: dict[int, dict[date, tuple[int, int]]] = {}
    for r in rows:
        days.setdefault(r.monitor_id, {})[r.day] = (r.total, r.down)

    latest = await session.execute(
        text("""
            SELECT DISTINCT ON (monitor_id) monitor_id, status
            FROM checks
            WHERE monitor_id = ANY(:ids) AND checked_at >= now() - INTERVAL '1 day'
            ORDER BY monitor_id, checked_at DESC
        """),
        {"ids": ids},
    )
    current = {r.monitor_id: r.status for r in latest}

    services = []
    for m in monitors:
        per_day = days.get(m.id, {})
        strip = []
        total_all = down_all = 0
        for i in range(DAYS):
            d = first_day + timedelta(days=i)
            total, down = per_day.get(d, (0, 0))
            total_all += total
            down_all += down
            strip.append({"date": d.isoformat(), "state": _day_state(total, down)})
        services.append(
            {
                "name": m.name,
                "status": current.get(m.id),
                "uptime_pct": round(100 * (total_all - down_all) / total_all, 3)
                if total_all
                else None,
                "days": strip,
            }
        )

    statuses = [s["status"] for s in services if s["status"]]
    overall = max(statuses, key=lambda s: SEVERITY[s]) if statuses else None
    names = {m.id: m.name for m in monitors}

    incidents = await session.execute(
        text("""
            SELECT monitor_id, started_at, resolved_at, duration_secs
            FROM incidents
            WHERE monitor_id = ANY(:ids) AND started_at >= now() - INTERVAL '30 days'
            ORDER BY started_at DESC
            LIMIT 10
        """),
        {"ids": ids},
    )

    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return {
        "title": page.title,
        "description": page.description,
        "overall_status": overall,
        "services": services,
        "incidents": [
            {
                "title": f"{names[i.monitor_id]} not responding",
                "started_at": i.started_at,
                "resolved_at": i.resolved_at,
                "duration_secs": i.duration_secs,
            }
            for i in incidents
        ],
        "updated_at": datetime.now(timezone.utc),
    }
