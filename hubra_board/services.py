"""Due dates, notice deadlines and the daily reminders."""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.function import FunctionHolder
from hubra.core.models.member import Member
from hubra.core.notifications.prefs import wants

from .models import BoardContract, BoardDuty, BoardMeeting, BoardTask

_log = logging.getLogger(__name__)

TOPIC = "tasks"
# A task due within this many days (or overdue) is reminded once.
TASK_SOON = 3
# The board hears this many days before the invitation deadline of a GV.
INVITE_WARN = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── Dates ────────────────────────────────────────────────────────────────────


def add_months(day: date, months: int) -> date:
    """*day* moved by whole months, kept to the month's last day."""
    total = day.year * 12 + day.month - 1 + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def duty_date(duty: BoardDuty, year: int) -> date:
    last = calendar.monthrange(year, duty.month)[1]
    return date(year, duty.month, min(duty.day, last))


def next_duty_date(duty: BoardDuty, today: date) -> date:
    this_year = duty_date(duty, today.year)
    return this_year if this_year >= today else duty_date(duty, today.year + 1)


def current_end(contract: BoardContract, today: date) -> date | None:
    """The end of the term running today: a contract that renews by itself
    moves on by its renewal period once its end has passed."""
    end = contract.ends_on
    if end is None:
        return None
    if contract.renews_months > 0:
        while end < today:
            end = add_months(end, contract.renews_months)
    return end


def notice_deadline(contract: BoardContract, today: date) -> date | None:
    """The next day by which notice can still be given. Once the deadline of
    the running term has passed, a contract that renews by itself has the
    next term's; one that doesn't simply ends and has none."""
    end = current_end(contract, today)
    if end is None or contract.ended:
        return None
    deadline = add_months(end, -contract.notice_months)
    if deadline < today and contract.renews_months > 0:
        deadline = add_months(
            add_months(end, contract.renews_months), -contract.notice_months
        )
    return deadline if deadline >= today else None


def expired(contract: BoardContract, today: date) -> bool:
    """A contract that doesn't renew and whose end has passed."""
    end = current_end(contract, today)
    return contract.ended or (end is not None and end < today)


def invite_by(meeting: BoardMeeting) -> date:
    return _aware(meeting.starts_at).date() - timedelta(days=meeting.invite_days)


# ── Who is responsible ───────────────────────────────────────────────────────


def function_ids_of(member_id: int) -> set[int]:
    return set(
        db.session.scalars(
            select(FunctionHolder.function_id).where(
                FunctionHolder.member_id == member_id
            )
        )
    )


def holders(function_id: int | None) -> list[int]:
    if function_id is None:
        return []
    return list(
        db.session.scalars(
            select(FunctionHolder.member_id).where(
                FunctionHolder.function_id == function_id
            )
        )
    )


def responsible(owner_id: int | None, function_id: int | None) -> list[int]:
    """The owner, else whoever holds the function today."""
    if owner_id:
        return [owner_id]
    return holders(function_id)


def is_mine(task: BoardTask, member_id: int) -> bool:
    return task.owner_id == member_id or (
        task.owner_id is None
        and task.function_id is not None
        and task.function_id in function_ids_of(member_id)
    )


# ── Notifications ────────────────────────────────────────────────────────────


def _german(member: Member) -> bool:
    return (getattr(member, "language", None) or "de").lower().startswith("de")


def _fmt(day: date, german: bool) -> str:
    return day.strftime("%d.%m.%Y") if german else day.isoformat()


def notify(
    member_ids,
    texts,
    link: str,
    topic: str | None = TOPIC,
) -> int:
    """Put a notification in each member's bell, in their language.

    *texts* is ``(german, english)``, each a function of ``german: bool``
    returning ``(title, message)``. Members who turned *topic* off are left
    out; a notification without a topic always comes.
    """
    from hubra.core.models.notification import Notification

    sent = 0
    ids = sorted({m for m in member_ids if m})
    if not ids:
        return 0
    for member in db.session.scalars(
        select(Member)
        .where(Member.id.in_(ids))
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
    ):
        if topic and not wants(member.notify_prefs, topic, "bell"):
            continue
        title, msg = texts(_german(member))
        notif = Notification(
            member_id=member.id,
            kind="info",
            title=title[:255],
            msg=msg[:255],
            link=link,
        )
        notif.topic = topic
        db.session.add(notif)
        sent += 1
    return sent


def all_active_ids() -> list[int]:
    return list(
        db.session.scalars(
            select(Member.id)
            .where(Member.status == "active")
            .where(Member.archived_at.is_(None))
        )
    )


# ── Daily run ────────────────────────────────────────────────────────────────


def _duties(today: date, done: dict) -> None:
    for duty in db.session.scalars(select(BoardDuty)):
        when = next_duty_date(duty, today)
        if duty.last_year == when.year or (when - today).days > duty.remind_days:
            continue
        task = BoardTask(
            title=duty.title,
            notes=duty.notes,
            owner_id=duty.owner_id,
            function_id=duty.function_id,
            due_on=when,
            duty_id=duty.id,
        )
        db.session.add(task)
        db.session.flush()
        duty.last_year = when.year
        done["duties"] += 1
        notify(
            responsible(duty.owner_id, duty.function_id),
            lambda de, t=duty.title, w=when: (
                (f"Jahresplan: {t}", f"Fällig am {_fmt(w, True)}")
                if de
                else (f"Year planner: {t}", f"Due on {_fmt(w, False)}")
            ),
            "/app/board",
        )


def _tasks(today: date, now: datetime, done: dict) -> None:
    soon = today + timedelta(days=TASK_SOON)
    for task in db.session.scalars(
        select(BoardTask)
        .where(BoardTask.done_at.is_(None))
        .where(BoardTask.reminded_at.is_(None))
        .where(BoardTask.due_on.isnot(None))
        .where(BoardTask.due_on <= soon)
        # A planner task was just announced; its reminder is that.
        .where(BoardTask.duty_id.is_(None))
    ):
        task.reminded_at = now
        done["tasks"] += 1
        late = task.due_on < today
        notify(
            responsible(task.owner_id, task.function_id),
            lambda de, t=task.title, d=task.due_on, late=late: (
                (
                    f"Aufgabe {'überfällig' if late else 'bald fällig'}: {t}",
                    f"Fällig am {_fmt(d, True)}",
                )
                if de
                else (
                    f"Task {'overdue' if late else 'due soon'}: {t}",
                    f"Due on {_fmt(d, False)}",
                )
            ),
            "/app/board",
        )


def _contracts(today: date, done: dict) -> None:
    for contract in db.session.scalars(
        select(BoardContract).where(BoardContract.ended.is_(False))
    ):
        deadline = notice_deadline(contract, today)
        if deadline is None or deadline < today:
            continue
        if contract.reminded_for == deadline:
            continue
        if (deadline - today).days > contract.remind_days:
            continue
        contract.reminded_for = deadline
        done["contracts"] += 1
        notify(
            responsible(contract.owner_id, contract.function_id),
            lambda de, t=contract.title, d=deadline: (
                (f"Kündigungsfrist: {t}", f"Kündigen bis {_fmt(d, True)}")
                if de
                else (f"Notice deadline: {t}", f"Give notice by {_fmt(d, False)}")
            ),
            "/app/board/contracts",
        )


def _meetings(today: date, now: datetime, done: dict) -> None:
    for meeting in db.session.scalars(
        select(BoardMeeting)
        .where(BoardMeeting.invited_at.is_(None))
        .where(BoardMeeting.closed_at.is_(None))
        .where(BoardMeeting.deadline_reminded_at.is_(None))
    ):
        by = invite_by(meeting)
        if by < today - timedelta(days=1) or (by - today).days > INVITE_WARN:
            continue
        meeting.deadline_reminded_at = now
        done["meetings"] += 1
        notify(
            [meeting.created_by],
            lambda de, t=meeting.title, d=by: (
                (f"Einladung verschicken: {t}", f"Laut Statuten bis {_fmt(d, True)}")
                if de
                else (f"Send the invitation: {t}", f"By {_fmt(d, False)} (statutes)")
            ),
            f"/app/board/meetings/{meeting.id}",
        )


def remind(today: date | None = None) -> dict:
    """Planner duties become tasks, and due tasks, notice deadlines and GV
    invitations are reminded. Each reminder goes once."""
    now = _now()
    today = today or now.date()
    done = {"duties": 0, "tasks": 0, "contracts": 0, "meetings": 0}
    _duties(today, done)
    _tasks(today, now, done)
    _contracts(today, done)
    _meetings(today, now, done)
    return done
