from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import get_settings
from .db import SessionLocal, engine
from .models import NIL_USER
from .routers import alerts, checks, incidents, monitors, reports, session, status, status_pages

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger("deploywatch")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # This month's partition must exist before anything writes a check.
    # Idempotent, so running it on every boot costs nothing.
    async with SessionLocal() as session:
        await session.execute(text("SELECT ensure_checks_partition(now()::date)"))
        # Data created before auth existed belongs to the owner.
        if settings.owner_user_id:
            for table in ("monitors", "status_pages"):
                await session.execute(
                    text(f"UPDATE {table} SET user_id = :owner WHERE user_id = :nil"),
                    {"owner": settings.owner_user_id, "nil": str(NIL_USER)},
                )
        await session.commit()
    if not settings.supabase_url:
        log.warning("SUPABASE_URL not set -- auth is OFF, every request is the owner")

    from .checker import scheduler

    try:
        scheduler.start()
        log.info("checker scheduler started")
    except NotImplementedError:
        # Expected until you build it. The API is fully usable without it --
        # seed.py provides check data in the meantime.
        log.warning("checker not wired up yet (app/checker/scheduler.py) -- API only")

    yield

    scheduler.shutdown()
    await engine.dispose()


app = FastAPI(title="DeployWatch", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(monitors.router)
app.include_router(checks.router)
app.include_router(incidents.router)
app.include_router(status.router)
app.include_router(alerts.router)
app.include_router(status_pages.router)
app.include_router(reports.router)
app.include_router(session.router)


@app.get("/api/health")
async def health():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"ok": True}
