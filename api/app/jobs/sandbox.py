"""Sweep sandbox sessions older than 5 minutes: their monitors (with checks,
incidents and alerts, by cascade), their status pages, the session row, and
the anonymous Supabase user itself."""

from __future__ import annotations

import logging

from sqlalchemy import text

from ..db import SessionLocal

log = logging.getLogger("deploywatch.sandbox")


async def sweep() -> None:
    async with SessionLocal() as session:
        expired = list(
            await session.scalars(
                text("""
                    DELETE FROM sandbox_sessions
                    WHERE started_at < now() - INTERVAL '5 minutes'
                    RETURNING user_id
                """)
            )
        )
        if not expired:
            await session.rollback()
            return
        await session.execute(text("DELETE FROM monitors WHERE user_id = ANY(:u)"), {"u": expired})
        await session.execute(text("DELETE FROM status_pages WHERE user_id = ANY(:u)"), {"u": expired})
        await session.commit()

    # Best effort: auth.users only exists on Supabase, and only the postgres
    # role can touch it. Anonymous users are otherwise never cleaned up.
    try:
        async with SessionLocal() as session:
            await session.execute(
                text("DELETE FROM auth.users WHERE id = ANY(:u) AND is_anonymous"),
                {"u": expired},
            )
            await session.commit()
    except Exception as exc:
        log.debug("skipping auth.users cleanup: %s", exc)

    log.info("swept %d expired sandbox session(s)", len(expired))
