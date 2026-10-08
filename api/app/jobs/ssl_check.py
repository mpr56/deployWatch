"""SSL certificate expiry for https monitors. Runs every 12 hours.

A separate TLS handshake rather than piggy-backing on the HTTP check: the
pooled httpx client does not reliably expose the peer certificate, and once a
day is plenty for something that changes every 90.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select, update

from ..db import SessionLocal
from ..models import Monitor

log = logging.getLogger("deploywatch.ssl")


async def cert_expiry(host: str, port: int = 443) -> datetime:
    ctx = ssl.create_default_context()
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ctx, server_hostname=host), timeout=10
    )
    try:
        cert = writer.get_extra_info("ssl_object").getpeercert()
        return datetime.fromtimestamp(
            ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc
        )
    finally:
        writer.close()


async def check_all() -> None:
    async with SessionLocal() as session:
        monitors = list(
            await session.scalars(
                select(Monitor).where(
                    Monitor.is_active.is_(True), Monitor.url.like("https://%")
                )
            )
        )

    async def one(m: Monitor) -> tuple[int, datetime | None, str | None]:
        parts = urlsplit(m.url)
        try:
            return m.id, await cert_expiry(parts.hostname, parts.port or 443), None
        except ssl.SSLCertVerificationError as exc:
            return m.id, None, exc.verify_message or "certificate verification failed"
        except Exception as exc:
            return m.id, None, f"{type(exc).__name__}: {exc}"[:200]

    results = await asyncio.gather(*(one(m) for m in monitors))
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        for mid, expires, error in results:
            await session.execute(
                update(Monitor)
                .where(Monitor.id == mid)
                .values(ssl_expires_at=expires, ssl_error=error, ssl_checked_at=now)
            )
        await session.commit()
    log.info("checked SSL for %d monitors", len(results))
