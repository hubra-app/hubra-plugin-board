"""Dashboard widgets of the board (docs/dashboards.md in hubra-app/hubra).

board.tasks     list  open tasks, the viewer's own by default, due first
board.meetings  list  the next meetings (GV), with date and place

They read as the viewing member, who needs ``board.tasks.read``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.permissions import member_has_permission

from . import services
from .models import BoardMeeting, BoardTask

MEETINGS = "board.meetings.update"


def _count(config: dict) -> int:
    try:
        return max(1, min(int(config.get("count") or 5), 20))
    except (TypeError, ValueError):
        return 5


def tasks(ctx, config: dict) -> dict:
    """Open tasks, due first; only the viewer's own unless ``mine`` is off."""
    rows = list(
        db.session.scalars(
            select(BoardTask)
            .where(BoardTask.done_at.is_(None))
            .order_by(BoardTask.due_on.is_(None), BoardTask.due_on, BoardTask.id)
            .limit(500)
        )
    )
    if config.get("mine", True) and ctx.actor is not None:
        rows = [t for t in rows if services.is_mine(t, ctx.actor.id)]
    items = [
        {
            "label": t.title,
            "sub": f"{t.due_on:%d.%m.%Y}" if t.due_on else None,
            "path": "/app/board",
        }
        for t in rows[: _count(config)]
    ]
    return {"items": items, "total": len(rows)}


def meetings(ctx, config: dict) -> dict:
    """Meetings still ahead; members without the right only invited ones."""
    query = (
        select(BoardMeeting)
        .where(BoardMeeting.starts_at >= datetime.now(timezone.utc))
        .where(BoardMeeting.closed_at.is_(None))
        .order_by(BoardMeeting.starts_at)
    )
    if ctx.actor is not None and not member_has_permission(ctx.actor, MEETINGS):
        query = query.where(BoardMeeting.invited_at.isnot(None))
    rows = list(db.session.scalars(query.limit(_count(config))))
    items = []
    for m in rows:
        when = services._aware(m.starts_at)
        sub = f"{when:%d.%m.%Y %H:%M}" + (f" · {m.place}" if m.place else "")
        items.append({"label": m.title, "sub": sub, "path": f"/app/board/meetings/{m.id}"})
    return {"items": items, "total": len(items)}
