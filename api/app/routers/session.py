"""Who am I, and the sandbox lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import SANDBOX_LIMITS, SANDBOX_TTL, Principal, auth_enabled, principal
from ..db import get_session
from ..models import SandboxSession

router = APIRouter(prefix="/api", tags=["session"])


async def _expiry(session: AsyncSession, p: Principal) -> datetime | None:
    if p.role != "sandbox":
        return None
    sess = await session.get(SandboxSession, p.user_id)
    return sess.started_at + SANDBOX_TTL if sess else None


@router.get("/me")
async def me(p: Principal = Depends(principal), session: AsyncSession = Depends(get_session)):
    return {
        "auth_enabled": auth_enabled(),
        "role": p.role,
        "can_edit": p.can_edit,
        "sandbox_expires_at": await _expiry(session, p),
        "sandbox_limits": SANDBOX_LIMITS,
    }


@router.post("/sandbox/start")
async def start_sandbox(
    p: Principal = Depends(principal), session: AsyncSession = Depends(get_session)
):
    """Record when this anonymous user's 5 minutes began. Idempotent."""
    if p.role != "sandbox":
        raise HTTPException(400, "sign in anonymously first")
    await session.execute(
        pg_insert(SandboxSession).values(user_id=p.user_id).on_conflict_do_nothing()
    )
    await session.commit()
    expires = await _expiry(session, p)
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(401, "sandbox expired")
    return {"sandbox_expires_at": expires}
