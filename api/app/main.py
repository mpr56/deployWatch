from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import get_settings
from .db import SessionLocal, engine
from .routers import alerts, checks, incidents, monitors, reports, status, status_pages

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
        await session.commit()

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


@app.get("/api/health")
async def health():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"ok": True}
