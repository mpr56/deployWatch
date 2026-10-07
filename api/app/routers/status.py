"""Public status page API. No auth, cacheable, deliberately minimal.

v3. Everything here is a TODO -- and it stays a TODO until v1 works end to end.
The status page is the prettiest screen in the product and building it early is
the classic way to never ship the boring parts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/{slug}")
async def public_status(slug: str):
    """Everything the public page renders, in one uncached-by-you response.

    TODO (you, v3):
      - Decide what `slug` addresses. `monitors` has no slug column: either add
        a `status_pages` table (slug, title, monitor ids) or put a slug on the
        user. A status page showing exactly one monitor is rarely what anyone
        wants, so probably the former.
      - Shape: {title, overall_status, services: [{name, status, days: [...]}],
        incidents: [...]}
      - `days` is 90 entries of daily uptime for the bar strips. Do NOT compute
        that from raw checks on every request -- 90 days x 1,440 checks x N
        monitors per page load. Roll it up nightly into a small table, or
        materialize it.
      - Return only name and status. No URLs, no error messages, no internals --
        this endpoint is unauthenticated and whatever it returns is public.
      - Set Cache-Control. This page gets hammered precisely when things break.
    """
    raise HTTPException(501, "not built yet -- app/routers/status.py:public_status")
