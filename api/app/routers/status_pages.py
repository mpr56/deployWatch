"""Admin CRUD for status pages: which monitors appear on which public slug."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    SANDBOX_LIMITS,
    Principal,
    editor,
    owned_by,
    owner_id,
    principal,
    visible_user_ids,
)
from ..db import get_session
from ..models import Monitor, StatusPage, StatusPageMonitor
from ..schemas import StatusPageIn, StatusPageOut

router = APIRouter(prefix="/api/status-pages", tags=["status-pages"])


async def _out(session: AsyncSession, page: StatusPage) -> StatusPageOut:
    ids = list(
        await session.scalars(
            select(StatusPageMonitor.monitor_id)
            .where(StatusPageMonitor.status_page_id == page.id)
            .order_by(StatusPageMonitor.position)
        )
    )
    return StatusPageOut(
        id=page.id, slug=page.slug, title=page.title,
        description=page.description, monitor_ids=ids,
        is_sandbox=page.user_id != owner_id(),
    )


async def _check_monitors(session: AsyncSession, ids: list[int], p: Principal) -> None:
    if not ids:
        return
    visible = set(
        await session.scalars(
            select(Monitor.id).where(
                Monitor.id.in_(ids), Monitor.user_id.in_(visible_user_ids(p))
            )
        )
    )
    if set(ids) - visible:
        raise HTTPException(404, "monitor not found")


async def _editable_page(session: AsyncSession, page_id: int, p: Principal) -> StatusPage:
    page = await session.get(StatusPage, page_id)
    if page is None or page.user_id not in visible_user_ids(p):
        raise HTTPException(404, "status page not found")
    if not owned_by(p, page.user_id):
        raise HTTPException(403, "sandbox can only change its own status pages")
    return page


async def _set_monitors(session: AsyncSession, page_id: int, ids: list[int]) -> None:
    await session.execute(
        delete(StatusPageMonitor).where(StatusPageMonitor.status_page_id == page_id)
    )
    for pos, mid in enumerate(dict.fromkeys(ids)):
        session.add(StatusPageMonitor(status_page_id=page_id, monitor_id=mid, position=pos))


@router.get("", response_model=list[StatusPageOut])
async def list_pages(
    session: AsyncSession = Depends(get_session), p: Principal = Depends(principal)
):
    pages = await session.scalars(
        select(StatusPage)
        .where(StatusPage.user_id.in_(visible_user_ids(p)))
        .order_by(StatusPage.id)
    )
    return [await _out(session, p) for p in pages.all()]


@router.post("", response_model=StatusPageOut, status_code=status.HTTP_201_CREATED)
async def create_page(
    payload: StatusPageIn,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
):
    if p.role == "sandbox":
        count = await session.scalar(
            select(func.count()).select_from(StatusPage).where(StatusPage.user_id == p.user_id)
        )
        if count >= SANDBOX_LIMITS["status_pages"]:
            raise HTTPException(429, "sandbox limit: 1 status page")
    await _check_monitors(session, payload.monitor_ids, p)
    page = StatusPage(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        user_id=owner_id() if p.role == "owner" else p.user_id,
    )
    session.add(page)
    try:
        await session.flush()
        await _set_monitors(session, page.id, payload.monitor_ids)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "that slug is taken, or a monitor no longer exists") from exc
    return await _out(session, page)


@router.put("/{page_id}", response_model=StatusPageOut)
async def update_page(
    page_id: int,
    payload: StatusPageIn,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
):
    page = await _editable_page(session, page_id, p)
    await _check_monitors(session, payload.monitor_ids, p)
    page.slug, page.title, page.description = payload.slug, payload.title, payload.description
    try:
        await _set_monitors(session, page.id, payload.monitor_ids)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "that slug is taken, or a monitor no longer exists") from exc
    return await _out(session, page)


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: int,
    session: AsyncSession = Depends(get_session),
    p: Principal = Depends(editor),
) -> None:
    await _editable_page(session, page_id, p)
    await session.execute(delete(StatusPage).where(StatusPage.id == page_id))
    await session.commit()
