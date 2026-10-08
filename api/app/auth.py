"""Who is calling, and what they may do.

Tokens are Supabase Auth JWTs. Three kinds of caller:

  visitor  -- no token. Read-only, sees the owner's data.
  owner    -- token whose `sub` is OWNER_USER_ID. Full control of owner data.
  sandbox  -- anonymous Supabase user (`is_anonymous: true`). Can create and
              change its own data only; everything is swept 5 minutes after the
              session starts (see jobs/sandbox.py).

Any other signed-in account is treated as a visitor for reads and refused for
writes -- sign-ups are not a way into the admin.

When SUPABASE_URL is unset (local dev), auth is off and every caller is the
owner, so the app works out of the box without a Supabase project.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_session
from .models import NIL_USER, Monitor, SandboxSession

SANDBOX_TTL = timedelta(minutes=5)
SANDBOX_LIMITS = {"monitors": 3, "webhooks": 2, "status_pages": 1}

Role = Literal["visitor", "owner", "sandbox", "other"]


@dataclass(frozen=True)
class Principal:
    role: Role
    user_id: uuid.UUID | None = None

    @property
    def can_edit(self) -> bool:
        return self.role in ("owner", "sandbox")


def auth_enabled() -> bool:
    return bool(get_settings().supabase_url)


def owner_id() -> uuid.UUID:
    s = get_settings()
    return uuid.UUID(s.owner_user_id) if s.owner_user_id else NIL_USER


def visible_user_ids(p: Principal) -> list[uuid.UUID]:
    """Whose data this caller can see: always the owner's, plus their own sandbox."""
    ids = [owner_id()]
    if p.role == "sandbox" and p.user_id:
        ids.append(p.user_id)
    return ids


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True)


async def _decode(token: str) -> dict:
    s = get_settings()
    if s.supabase_jwt_secret:  # legacy HS256 projects
        return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    key = await asyncio.to_thread(lambda: _jwks_client().get_signing_key_from_jwt(token))
    return jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience="authenticated")


async def principal(request: Request) -> Principal:
    if not auth_enabled():
        return Principal("owner", owner_id())

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return Principal("visitor")
    try:
        claims = await _decode(header[7:])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")

    sub = uuid.UUID(claims["sub"])
    if claims.get("is_anonymous"):
        return Principal("sandbox", sub)
    if get_settings().owner_user_id and sub == owner_id():
        return Principal("owner", sub)
    return Principal("other", sub)


async def editor(
    p: Principal = Depends(principal), session: AsyncSession = Depends(get_session)
) -> Principal:
    """Dependency for every write route."""
    if p.role == "visitor":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in or start a sandbox to make changes")
    if p.role == "other":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this account is not the admin")
    if p.role == "sandbox":
        sess = await session.get(SandboxSession, p.user_id)
        if sess is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "sandbox not started")
        if sess.started_at + SANDBOX_TTL < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sandbox expired")
    return p


def owned_by(p: Principal, user_id: uuid.UUID) -> bool:
    """May this editor change a row owned by user_id?"""
    return user_id == (owner_id() if p.role == "owner" else p.user_id)


# --- outbound URL safety ------------------------------------------------------

async def assert_public_url(url: str) -> None:
    """Refuse URLs that resolve to private, loopback or link-local addresses.

    Monitors and webhooks make this server send requests on someone's behalf;
    without this, anyone with edit access could probe the host's network or a
    cloud metadata endpoint. Off when ALLOW_PRIVATE_TARGETS=true (local dev).
    """
    if get_settings().allow_private_targets:
        return
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(422, "URL must be http(s) with a host")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        raise HTTPException(422, f"cannot resolve {parts.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise HTTPException(422, "URL points at a private or internal address")


async def visible_monitor(session: AsyncSession, monitor_id: int, p: Principal) -> Monitor:
    """The monitor, or 404 if it does not exist or this caller cannot see it."""
    m = await session.get(Monitor, monitor_id)
    if m is None or m.user_id not in visible_user_ids(p):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "monitor not found")
    return m


async def editable_monitor(session: AsyncSession, monitor_id: int, p: Principal) -> Monitor:
    m = await visible_monitor(session, monitor_id, p)
    if not owned_by(p, m.user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sandbox can only change its own monitors")
    return m
