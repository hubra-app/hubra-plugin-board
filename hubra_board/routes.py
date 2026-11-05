"""Board API: /api/v1/app/board.

GET    /options                       functions and polls to choose from
GET    /tasks?show=open|done|mine     tasks
POST   /tasks                         {title, notes?, ownerId?, functionId?, dueOn?}
PATCH  /tasks/<id>                    same fields
POST   /tasks/<id>/done               {done}: also the task's owner or holder
DELETE /tasks/<id>
GET    /duties                        the year planner
POST   /duties                        {title, month, day, ownerId?, functionId?, remindDays?, notes?}
PATCH  /duties/<id>
DELETE /duties/<id>
GET    /contracts                     contracts and insurances, with deadlines
POST   /contracts                     {title, kind, party?, cost?, costPeriod?, endsOn?, ...}
PATCH  /contracts/<id>
DELETE /contracts/<id>
GET    /meetings                      board: all; members: those they were invited to
POST   /meetings                      {title, startsAt, place?, inviteDays?, quorum?, intro?}
GET    /meetings/<id>
PATCH  /meetings/<id>
DELETE /meetings/<id>
POST   /meetings/<id>/agenda          {title, description?, pollId?}
PUT    /meetings/<id>/agenda/order    {ids}
PATCH  /agenda/<id>                   {title?, description?, pollId?, minutes?, decision?}
DELETE /agenda/<id>
POST   /meetings/<id>/invite          every active member gets the invitation
GET    /meetings/<id>/attendance      members with present or not
PUT    /meetings/<id>/attendance/<member_id>    sign in
DELETE /meetings/<id>/attendance/<member_id>    sign out
POST   /meetings/<id>/close           {reopen?}
GET    /meetings/<id>/invitation.pdf  for the invited
GET    /meetings/<id>/minutes.pdf     board; members once the meeting is closed
"""

from __future__ import annotations

import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func, select

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.function import Function
from hubra.core.models.member import Member
from hubra.core.models.poll import Poll
from hubra.core.permissions import (
    member_has_permission,
    permission_required,
    require_member,
)
from hubra.core.utils import log_audit

from . import pdf, services
from .models import (
    BoardAgendaItem,
    BoardAttendance,
    BoardContract,
    BoardDuty,
    BoardMeeting,
    BoardTask,
)

board_bp = Blueprint("board_bp", __name__)

MEETINGS = "board.meetings.update"
KINDS = ("insurance", "rent", "licence", "service", "membership", "other")
PERIODS = ("year", "quarter", "month", "once")


class Invalid(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@board_bp.errorhandler(Invalid)
def _invalid(exc: Invalid):
    return api_error("VALIDATION_ERROR", exc.message, 400)


# ── Reading the body ─────────────────────────────────────────────────────────


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _text(data: dict, key: str, limit: int, required: bool = False) -> str | None:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise Invalid(f"{key} is required")
        return None
    if not isinstance(value, str):
        raise Invalid(f"{key} must be text")
    value = value.strip()
    if len(value) > limit:
        raise Invalid(f"{key} is longer than {limit} characters")
    return value


def _int(data: dict, key: str, low: int, high: int, default=None) -> int | None:
    value = data.get(key, default)
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise Invalid(f"{key} must be a whole number") from None
    if not low <= number <= high:
        raise Invalid(f"{key} must be between {low} and {high}")
    return number


def _date(data: dict, key: str) -> date | None:
    value = data.get(key)
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise Invalid(f"{key} must be a date (YYYY-MM-DD)") from None


def _datetime(data: dict, key: str) -> datetime | None:
    value = data.get(key)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise Invalid(f"{key} must be a date and time") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _money(data: dict, key: str) -> Decimal | None:
    value = data.get(key)
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise Invalid(f"{key} must be an amount") from None
    if amount < 0 or amount >= Decimal("10000000000"):
        raise Invalid(f"{key} is out of range")
    return amount


def _member_id(data: dict, key: str) -> int | None:
    value = _int(data, key, 1, 2**31 - 1)
    if value is not None and db.session.get(Member, value) is None:
        raise Invalid(f"{key}: no such member")
    return value


def _function_id(data: dict, key: str) -> int | None:
    value = _int(data, key, 1, 2**31 - 1)
    if value is not None and db.session.get(Function, value) is None:
        raise Invalid(f"{key}: no such function")
    return value


def _poll_id(data: dict) -> int | None:
    value = _int(data, "pollId", 1, 2**31 - 1)
    if value is not None and db.session.get(Poll, value) is None:
        raise Invalid("pollId: no such poll")
    return value


def _who(data: dict, row, partial: bool) -> None:
    """ownerId / functionId: a person, or a function and its holders."""
    if not partial or "ownerId" in data:
        row.owner_id = _member_id(data, "ownerId")
    if not partial or "functionId" in data:
        row.function_id = _function_id(data, "functionId")


# ── Output ───────────────────────────────────────────────────────────────────


def _names(ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        m.id: m.name
        for m in db.session.scalars(select(Member).where(Member.id.in_(ids)))
    }


def _functions() -> dict[int, str]:
    return {f.id: f.name for f in db.session.scalars(select(Function))}


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _task(task: BoardTask, names: dict, functions: dict, me: int) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "notes": task.notes,
        "ownerId": task.owner_id,
        "ownerName": names.get(task.owner_id or 0),
        "functionId": task.function_id,
        "functionName": functions.get(task.function_id or 0),
        "dueOn": _iso(task.due_on),
        "done": task.done_at is not None,
        "doneAt": _iso(task.done_at),
        "doneByName": names.get(task.done_by or 0),
        "fromPlanner": task.duty_id is not None,
        "mine": services.is_mine(task, me),
    }


def _duty(duty: BoardDuty, names: dict, functions: dict, today: date) -> dict:
    return {
        "id": duty.id,
        "title": duty.title,
        "notes": duty.notes,
        "month": duty.month,
        "day": duty.day,
        "next": services.next_duty_date(duty, today).isoformat(),
        "ownerId": duty.owner_id,
        "ownerName": names.get(duty.owner_id or 0),
        "functionId": duty.function_id,
        "functionName": functions.get(duty.function_id or 0),
        "remindDays": duty.remind_days,
    }


def _contract(c: BoardContract, names: dict, functions: dict, today: date) -> dict:
    end = services.current_end(c, today)
    deadline = services.notice_deadline(c, today)
    return {
        "id": c.id,
        "title": c.title,
        "kind": c.kind,
        "party": c.party,
        "reference": c.reference,
        "cost": float(c.cost) if c.cost is not None else None,
        "costPeriod": c.cost_period,
        "startsOn": _iso(c.starts_on),
        "endsOn": _iso(c.ends_on),
        "currentEnd": _iso(end),
        "noticeMonths": c.notice_months,
        "renewsMonths": c.renews_months,
        "noticeBy": _iso(deadline),
        "daysLeft": (deadline - today).days if deadline else None,
        "remindDays": c.remind_days,
        "ownerId": c.owner_id,
        "ownerName": names.get(c.owner_id or 0),
        "functionId": c.function_id,
        "functionName": functions.get(c.function_id or 0),
        "notes": c.notes,
        "ended": c.ended,
        "expired": services.expired(c, today),
    }


def _present(meeting_id: int) -> int:
    return (
        db.session.scalar(
            select(func.count(BoardAttendance.id)).where(
                BoardAttendance.meeting_id == meeting_id
            )
        )
        or 0
    )


def _meeting(m: BoardMeeting, me: int | None = None, full: bool = False) -> dict:
    present = _present(m.id)
    out = {
        "id": m.id,
        "title": m.title,
        "startsAt": _iso(services._aware(m.starts_at)),
        "place": m.place,
        "inviteDays": m.invite_days,
        "inviteBy": services.invite_by(m).isoformat(),
        "quorum": m.quorum,
        "present": present,
        "quorate": present >= m.quorum if m.quorum else None,
        "invitedAt": _iso(m.invited_at),
        "closedAt": _iso(m.closed_at),
        "chair": m.chair,
        "minuteTaker": m.minute_taker,
    }
    if full:
        out["intro"] = m.intro
        items = _items(m.id)
        polls = {
            p.id: p
            for p in db.session.scalars(
                select(Poll).where(Poll.id.in_([i.poll_id for i in items if i.poll_id]))
            )
        }
        out["agenda"] = [
            {
                "id": i.id,
                "position": n,
                "title": i.title,
                "description": i.description,
                "pollId": i.poll_id,
                "pollQuestion": polls[i.poll_id].question
                if i.poll_id in polls
                else None,
                "pollStatus": polls[i.poll_id].status if i.poll_id in polls else None,
                "minutes": i.minutes,
                "decision": i.decision,
            }
            for n, i in enumerate(items, start=1)
        ]
        if me is not None:
            out["iAmPresent"] = (
                db.session.scalar(
                    select(BoardAttendance.id).where(
                        BoardAttendance.meeting_id == m.id,
                        BoardAttendance.member_id == me,
                    )
                )
                is not None
            )
    return out


def _items(meeting_id: int) -> list[BoardAgendaItem]:
    return list(
        db.session.scalars(
            select(BoardAgendaItem)
            .where(BoardAgendaItem.meeting_id == meeting_id)
            .order_by(BoardAgendaItem.position, BoardAgendaItem.id)
        )
    )


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _get(model, row_id: int):
    row = db.session.get(model, row_id)
    if row is None:
        return None, api_error("NOT_FOUND", "Not found", 404)
    return row, None


# ── Options ──────────────────────────────────────────────────────────────────


@board_bp.get("/options")
@require_member
def options():
    member = get_current_member()
    can = {
        "tasks": member_has_permission(member, "board.tasks.update"),
        "tasksRead": member_has_permission(member, "board.tasks.read"),
        "contracts": member_has_permission(member, "board.contracts.update"),
        "contractsRead": member_has_permission(member, "board.contracts.read"),
        "meetings": member_has_permission(member, MEETINGS),
    }
    out: dict = {"can": can, "memberId": member.id}
    if can["tasksRead"] or can["meetings"]:
        out["functions"] = [
            {"id": fid, "name": name}
            for fid, name in sorted(_functions().items(), key=lambda x: x[1].lower())
        ]
    if can["meetings"]:
        out["polls"] = [
            {"id": p.id, "question": p.question, "status": p.status}
            for p in db.session.scalars(
                select(Poll).order_by(Poll.id.desc()).limit(100)
            )
        ]
    return jsonify(out)


# ── Tasks ────────────────────────────────────────────────────────────────────


@board_bp.get("/tasks")
@permission_required("tasks", "read", "See the board's tasks and year planner")
def list_tasks():
    me = get_current_member().id
    show = request.args.get("show", "open")
    query = select(BoardTask)
    if show == "done":
        query = query.where(BoardTask.done_at.isnot(None)).order_by(
            BoardTask.done_at.desc()
        )
    else:
        query = query.where(BoardTask.done_at.is_(None)).order_by(
            BoardTask.due_on.is_(None), BoardTask.due_on, BoardTask.id
        )
    tasks = list(db.session.scalars(query.limit(500)))
    if show == "mine":
        tasks = [t for t in tasks if services.is_mine(t, me)]
    names = _names([t.owner_id for t in tasks] + [t.done_by for t in tasks])
    functions = _functions()
    return jsonify([_task(t, names, functions, me) for t in tasks])


def _apply_task(task: BoardTask, data: dict, partial: bool) -> None:
    if not partial or "title" in data:
        task.title = _text(data, "title", 200, required=True)
    if not partial or "notes" in data:
        task.notes = _text(data, "notes", 5000)
    if not partial or "dueOn" in data:
        task.due_on = _date(data, "dueOn")
        task.reminded_at = None
    _who(data, task, partial)


@board_bp.post("/tasks")
@permission_required("tasks", "update", "Add and change the board's tasks")
def create_task():
    member = get_current_member()
    task = BoardTask(created_by=member.id)
    _apply_task(task, _body(), partial=False)
    db.session.add(task)
    db.session.flush()
    if task.owner_id and task.owner_id != member.id:
        services.notify(
            [task.owner_id],
            lambda de, t=task.title: (
                ("Neue Aufgabe für dich", t) if de else ("A new task for you", t)
            ),
            "/app/board",
        )
    db.session.commit()
    return jsonify(_task(task, _names([task.owner_id]), _functions(), member.id)), 201


@board_bp.patch("/tasks/<int:task_id>")
@permission_required("tasks", "update", "Add and change the board's tasks")
def update_task(task_id: int):
    task, err = _get(BoardTask, task_id)
    if err:
        return err
    _apply_task(task, _body(), partial=True)
    db.session.commit()
    me = get_current_member().id
    return jsonify(_task(task, _names([task.owner_id, task.done_by]), _functions(), me))


def _own_task(member, task_id: int, **_kw):
    task = db.session.get(BoardTask, task_id)
    if task is not None and member is not None and services.is_mine(task, member.id):
        return "owner"
    return None


@board_bp.post("/tasks/<int:task_id>/done")
@permission_required(
    "tasks", "update", "Add and change the board's tasks", allow=_own_task
)
def finish_task(task_id: int):
    task, err = _get(BoardTask, task_id)
    if err:
        return err
    member = get_current_member()
    if _body().get("done", True):
        if task.done_at is None:
            task.done_at = datetime.now(timezone.utc)
            task.done_by = member.id
    else:
        task.done_at = None
        task.done_by = None
    db.session.commit()
    return jsonify(
        _task(task, _names([task.owner_id, task.done_by]), _functions(), member.id)
    )


@board_bp.delete("/tasks/<int:task_id>")
@permission_required("tasks", "update", "Add and change the board's tasks")
def delete_task(task_id: int):
    task, err = _get(BoardTask, task_id)
    if err:
        return err
    db.session.delete(task)
    db.session.commit()
    return "", 204


# ── Year planner ─────────────────────────────────────────────────────────────


@board_bp.get("/duties")
@permission_required("tasks", "read", "See the board's tasks and year planner")
def list_duties():
    today = _today()
    duties = list(db.session.scalars(select(BoardDuty)))
    duties.sort(key=lambda d: services.next_duty_date(d, today))
    names = _names([d.owner_id for d in duties])
    functions = _functions()
    return jsonify([_duty(d, names, functions, today) for d in duties])


def _apply_duty(duty: BoardDuty, data: dict, partial: bool) -> None:
    if not partial or "title" in data:
        duty.title = _text(data, "title", 200, required=True)
    if not partial or "notes" in data:
        duty.notes = _text(data, "notes", 5000)
    if not partial or "month" in data or "day" in data:
        month = _int(data, "month", 1, 12, duty.month)
        day = _int(data, "day", 1, 31, duty.day)
        if month is None or day is None:
            raise Invalid("month and day are required")
        duty.month, duty.day = month, day
        duty.last_year = None
    if not partial or "remindDays" in data:
        duty.remind_days = _int(data, "remindDays", 0, 180, 14)
    _who(data, duty, partial)


@board_bp.post("/duties")
@permission_required("tasks", "update", "Add and change the board's tasks")
def create_duty():
    duty = BoardDuty()
    _apply_duty(duty, _body(), partial=False)
    db.session.add(duty)
    db.session.commit()
    return (
        jsonify(_duty(duty, _names([duty.owner_id]), _functions(), _today())),
        201,
    )


@board_bp.patch("/duties/<int:duty_id>")
@permission_required("tasks", "update", "Add and change the board's tasks")
def update_duty(duty_id: int):
    duty, err = _get(BoardDuty, duty_id)
    if err:
        return err
    _apply_duty(duty, _body(), partial=True)
    db.session.commit()
    return jsonify(_duty(duty, _names([duty.owner_id]), _functions(), _today()))


@board_bp.delete("/duties/<int:duty_id>")
@permission_required("tasks", "update", "Add and change the board's tasks")
def delete_duty(duty_id: int):
    duty, err = _get(BoardDuty, duty_id)
    if err:
        return err
    db.session.delete(duty)
    db.session.commit()
    return "", 204


# ── Contracts ────────────────────────────────────────────────────────────────


@board_bp.get("/contracts")
@permission_required("contracts", "read", "See contracts and insurances")
def list_contracts():
    today = _today()
    rows = list(db.session.scalars(select(BoardContract)))
    far = date.max

    def order(c: BoardContract):
        deadline = services.notice_deadline(c, today)
        return (services.expired(c, today), deadline or far, c.title.lower())

    rows.sort(key=order)
    names = _names([c.owner_id for c in rows])
    functions = _functions()
    return jsonify([_contract(c, names, functions, today) for c in rows])


def _apply_contract(c: BoardContract, data: dict, partial: bool) -> None:
    if not partial or "title" in data:
        c.title = _text(data, "title", 200, required=True)
    if not partial or "kind" in data:
        kind = data.get("kind") or "other"
        if kind not in KINDS:
            raise Invalid(f"kind must be one of {', '.join(KINDS)}")
        c.kind = kind
    for key, attr, limit in (
        ("party", "party", 200),
        ("reference", "reference", 100),
        ("notes", "notes", 5000),
    ):
        if not partial or key in data:
            setattr(c, attr, _text(data, key, limit))
    if not partial or "cost" in data:
        c.cost = _money(data, "cost")
    if not partial or "costPeriod" in data:
        period = data.get("costPeriod") or "year"
        if period not in PERIODS:
            raise Invalid(f"costPeriod must be one of {', '.join(PERIODS)}")
        c.cost_period = period
    if not partial or "startsOn" in data:
        c.starts_on = _date(data, "startsOn")
    if not partial or "endsOn" in data:
        c.ends_on = _date(data, "endsOn")
    if not partial or "noticeMonths" in data:
        c.notice_months = _int(data, "noticeMonths", 0, 60, 0)
    if not partial or "renewsMonths" in data:
        c.renews_months = _int(data, "renewsMonths", 0, 120, 12)
    if not partial or "remindDays" in data:
        c.remind_days = _int(data, "remindDays", 0, 365, 30)
    if not partial or "ended" in data:
        c.ended = bool(data.get("ended", False))
    _who(data, c, partial)
    if c.starts_on and c.ends_on and c.ends_on < c.starts_on:
        raise Invalid("endsOn is before startsOn")


@board_bp.post("/contracts")
@permission_required("contracts", "update", "Add and change contracts and insurances")
def create_contract():
    c = BoardContract()
    _apply_contract(c, _body(), partial=False)
    db.session.add(c)
    db.session.flush()
    log_audit(
        get_current_member().id,
        "board.contract.created",
        "board_contract",
        c.id,
        c.title,
    )
    db.session.commit()
    return jsonify(_contract(c, _names([c.owner_id]), _functions(), _today())), 201


@board_bp.patch("/contracts/<int:contract_id>")
@permission_required("contracts", "update", "Add and change contracts and insurances")
def update_contract(contract_id: int):
    c, err = _get(BoardContract, contract_id)
    if err:
        return err
    _apply_contract(c, _body(), partial=True)
    db.session.commit()
    return jsonify(_contract(c, _names([c.owner_id]), _functions(), _today()))


@board_bp.delete("/contracts/<int:contract_id>")
@permission_required("contracts", "update", "Add and change contracts and insurances")
def delete_contract(contract_id: int):
    c, err = _get(BoardContract, contract_id)
    if err:
        return err
    log_audit(
        get_current_member().id,
        "board.contract.deleted",
        "board_contract",
        c.id,
        c.title,
    )
    db.session.delete(c)
    db.session.commit()
    return "", 204


# ── Meetings ─────────────────────────────────────────────────────────────────


def _can_see(meeting: BoardMeeting, member) -> bool:
    return meeting.invited_at is not None or member_has_permission(member, MEETINGS)


@board_bp.get("/meetings")
@require_member
def list_meetings():
    member = get_current_member()
    query = select(BoardMeeting).order_by(BoardMeeting.starts_at.desc())
    if not member_has_permission(member, MEETINGS):
        query = query.where(BoardMeeting.invited_at.isnot(None))
    return jsonify([_meeting(m) for m in db.session.scalars(query.limit(200))])


def _apply_meeting(m: BoardMeeting, data: dict, partial: bool) -> None:
    if not partial or "title" in data:
        m.title = _text(data, "title", 200, required=True)
    if not partial or "startsAt" in data:
        starts = _datetime(data, "startsAt")
        if starts is None:
            raise Invalid("startsAt is required")
        m.starts_at = starts
        m.deadline_reminded_at = None
    for key, attr, limit in (
        ("place", "place", 300),
        ("intro", "intro", 20000),
        ("chair", "chair", 200),
        ("minuteTaker", "minute_taker", 200),
    ):
        if not partial or key in data:
            setattr(m, attr, _text(data, key, limit))
    if not partial or "inviteDays" in data:
        m.invite_days = _int(data, "inviteDays", 0, 120, 20)
    if not partial or "quorum" in data:
        m.quorum = _int(data, "quorum", 0, 100000, 0)


@board_bp.post("/meetings")
@permission_required("meetings", "update", "Prepare and run general meetings")
def create_meeting():
    member = get_current_member()
    m = BoardMeeting(created_by=member.id)
    data = _body()
    _apply_meeting(m, data, partial=False)
    db.session.add(m)
    db.session.flush()
    # The usual agenda of an ordinary GV, to change as needed.
    if data.get("standardAgenda"):
        for pos, title in enumerate(standard_agenda(member), start=1):
            db.session.add(BoardAgendaItem(meeting_id=m.id, position=pos, title=title))
    log_audit(member.id, "board.meeting.created", "board_meeting", m.id, m.title)
    db.session.commit()
    return jsonify(_meeting(m, member.id, full=True)), 201


def standard_agenda(member) -> list[str]:
    if (getattr(member, "language", None) or "de").lower().startswith("de"):
        return [
            "Begrüssung und Wahl der Stimmenzähler",
            "Protokoll der letzten Generalversammlung",
            "Jahresbericht des Vorstands",
            "Jahresrechnung und Bericht der Revisoren",
            "Entlastung des Vorstands",
            "Budget und Mitgliederbeiträge",
            "Wahlen",
            "Anträge",
            "Verschiedenes",
        ]
    return [
        "Welcome and election of the vote counters",
        "Minutes of the last general meeting",
        "Annual report of the board",
        "Annual accounts and the auditors' report",
        "Discharge of the board",
        "Budget and membership fees",
        "Elections",
        "Motions",
        "Any other business",
    ]


@board_bp.get("/meetings/<int:meeting_id>")
@require_member
def get_meeting(meeting_id: int):
    member = get_current_member()
    m = db.session.get(BoardMeeting, meeting_id)
    if m is None or not _can_see(m, member):
        return api_error("NOT_FOUND", "Not found", 404)
    out = _meeting(m, member.id, full=True)
    out["canManage"] = member_has_permission(member, MEETINGS)
    return jsonify(out)


@board_bp.patch("/meetings/<int:meeting_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def update_meeting(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    _apply_meeting(m, _body(), partial=True)
    db.session.commit()
    return jsonify(_meeting(m, get_current_member().id, full=True))


@board_bp.delete("/meetings/<int:meeting_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def delete_meeting(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    log_audit(
        get_current_member().id, "board.meeting.deleted", "board_meeting", m.id, m.title
    )
    db.session.delete(m)
    db.session.commit()
    return "", 204


@board_bp.post("/meetings/<int:meeting_id>/agenda")
@permission_required("meetings", "update", "Prepare and run general meetings")
def add_item(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    data = _body()
    last = db.session.scalar(
        select(func.max(BoardAgendaItem.position)).where(
            BoardAgendaItem.meeting_id == m.id
        )
    )
    item = BoardAgendaItem(
        meeting_id=m.id,
        position=(last or 0) + 1,
        title=_text(data, "title", 300, required=True),
        description=_text(data, "description", 20000),
        poll_id=_poll_id(data),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(_meeting(m, get_current_member().id, full=True)), 201


@board_bp.put("/meetings/<int:meeting_id>/agenda/order")
@permission_required("meetings", "update", "Prepare and run general meetings")
def order_items(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    ids = _body().get("ids")
    items = {i.id: i for i in _items(m.id)}
    if not isinstance(ids, list) or sorted(ids) != sorted(items):
        raise Invalid("ids must list every agenda item of the meeting once")
    for pos, item_id in enumerate(ids, start=1):
        items[item_id].position = pos
    db.session.commit()
    return jsonify(_meeting(m, get_current_member().id, full=True))


@board_bp.patch("/agenda/<int:item_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def update_item(item_id: int):
    item, err = _get(BoardAgendaItem, item_id)
    if err:
        return err
    data = _body()
    if "title" in data:
        item.title = _text(data, "title", 300, required=True)
    for key, limit in (("description", 20000), ("minutes", 50000), ("decision", 5000)):
        if key in data:
            setattr(item, key, _text(data, key, limit))
    if "pollId" in data:
        item.poll_id = _poll_id(data)
    db.session.commit()
    m = db.session.get(BoardMeeting, item.meeting_id)
    return jsonify(_meeting(m, get_current_member().id, full=True))


@board_bp.delete("/agenda/<int:item_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def delete_item(item_id: int):
    item, err = _get(BoardAgendaItem, item_id)
    if err:
        return err
    meeting_id = item.meeting_id
    db.session.delete(item)
    db.session.flush()
    for pos, rest in enumerate(_items(meeting_id), start=1):
        rest.position = pos
    db.session.commit()
    return "", 204


@board_bp.post("/meetings/<int:meeting_id>/invite")
@permission_required("meetings", "update", "Prepare and run general meetings")
def invite(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    if m.invited_at is not None:
        return api_error("ALREADY_INVITED", "The invitation went out already", 409)
    if not _items(m.id):
        return api_error("NO_AGENDA", "Add the agenda before inviting", 409)
    member = get_current_member()
    m.invited_at = datetime.now(timezone.utc)
    when = services._aware(m.starts_at).astimezone(ZoneInfo("Europe/Zurich"))
    late = services.invite_by(m) < _today()

    def texts(de: bool):
        day = when.strftime("%d.%m.%Y %H:%M") if de else when.strftime("%Y-%m-%d %H:%M")
        where = f" · {m.place}" if m.place else ""
        return (
            (f"Einladung: {m.title}", f"{day}{where}")
            if de
            else (f"Invitation: {m.title}", f"{day}{where}")
        )

    # An invitation to the general meeting comes whatever the member chose
    # for the bell: no topic.
    sent = services.notify(
        services.all_active_ids(), texts, f"/app/board/meetings/{m.id}", topic=None
    )
    log_audit(
        member.id,
        "board.meeting.invited",
        "board_meeting",
        m.id,
        f"{m.title}: {sent} members",
    )
    db.session.commit()
    out = _meeting(m, member.id, full=True)
    out["sent"] = sent
    out["late"] = late
    return jsonify(out)


@board_bp.get("/meetings/<int:meeting_id>/attendance")
@permission_required("meetings", "update", "Prepare and run general meetings")
def attendance(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    present = {
        a.member_id: a
        for a in db.session.scalars(
            select(BoardAttendance).where(BoardAttendance.meeting_id == m.id)
        )
    }
    members = list(
        db.session.scalars(
            select(Member)
            .where(Member.status == "active")
            .where(Member.archived_at.is_(None))
        )
    )
    # Someone signed in who has since left stays on the list.
    missing = set(present) - {mb.id for mb in members}
    if missing:
        members += list(
            db.session.scalars(select(Member).where(Member.id.in_(missing)))
        )
    rows = [
        {
            "memberId": mb.id,
            "name": mb.name,
            "present": mb.id in present,
            "signedInAt": _iso(present[mb.id].signed_in_at)
            if mb.id in present
            else None,
        }
        for mb in members
    ]
    rows.sort(key=lambda r: r["name"].lower())
    return jsonify({"present": len(present), "quorum": m.quorum, "members": rows})


@board_bp.put("/meetings/<int:meeting_id>/attendance/<int:member_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def sign_in(meeting_id: int, member_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    if m.closed_at is not None:
        return api_error("MEETING_CLOSED", "The meeting is closed", 409)
    if db.session.get(Member, member_id) is None:
        return api_error("NOT_FOUND", "No such member", 404)
    exists = db.session.scalar(
        select(BoardAttendance.id).where(
            BoardAttendance.meeting_id == m.id, BoardAttendance.member_id == member_id
        )
    )
    if exists is None:
        db.session.add(
            BoardAttendance(
                meeting_id=m.id,
                member_id=member_id,
                signed_in_by=get_current_member().id,
            )
        )
        db.session.commit()
    present = _present(m.id)
    return jsonify(
        {"present": present, "quorate": present >= m.quorum if m.quorum else None}
    )


@board_bp.delete("/meetings/<int:meeting_id>/attendance/<int:member_id>")
@permission_required("meetings", "update", "Prepare and run general meetings")
def sign_out(meeting_id: int, member_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    if m.closed_at is not None:
        return api_error("MEETING_CLOSED", "The meeting is closed", 409)
    row = db.session.scalar(
        select(BoardAttendance).where(
            BoardAttendance.meeting_id == m.id, BoardAttendance.member_id == member_id
        )
    )
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    present = _present(m.id)
    return jsonify(
        {"present": present, "quorate": present >= m.quorum if m.quorum else None}
    )


@board_bp.post("/meetings/<int:meeting_id>/close")
@permission_required("meetings", "update", "Prepare and run general meetings")
def close(meeting_id: int):
    m, err = _get(BoardMeeting, meeting_id)
    if err:
        return err
    member = get_current_member()
    if _body().get("reopen"):
        m.closed_at = None
        log_audit(member.id, "board.meeting.reopened", "board_meeting", m.id, m.title)
    elif m.closed_at is None:
        m.closed_at = datetime.now(timezone.utc)
        log_audit(member.id, "board.meeting.closed", "board_meeting", m.id, m.title)
    db.session.commit()
    return jsonify(_meeting(m, member.id, full=True))


def _pdf_response(data: bytes, name: str, inline: bool):
    return send_file(
        io.BytesIO(data),
        mimetype="application/pdf",
        as_attachment=not inline,
        download_name=name,
    )


def _slug(title: str) -> str:
    keep = "".join(ch if ch.isalnum() else "-" for ch in title.lower())
    return "-".join(p for p in keep.split("-") if p)[:60] or "gv"


@board_bp.get("/meetings/<int:meeting_id>/invitation.pdf")
@require_member
def invitation_pdf(meeting_id: int):
    member = get_current_member()
    m = db.session.get(BoardMeeting, meeting_id)
    if m is None or not _can_see(m, member):
        return api_error("NOT_FOUND", "Not found", 404)
    data = pdf.invitation(m, _items(m.id), member.language)
    return _pdf_response(
        data, f"einladung-{_slug(m.title)}.pdf", request.args.get("inline") == "1"
    )


@board_bp.get("/meetings/<int:meeting_id>/minutes.pdf")
@require_member
def minutes_pdf(meeting_id: int):
    member = get_current_member()
    m = db.session.get(BoardMeeting, meeting_id)
    manager = member_has_permission(member, MEETINGS)
    if m is None or not (manager or (m.invited_at and m.closed_at)):
        return api_error("NOT_FOUND", "Not found", 404)
    present = [
        mb.name
        for mb in db.session.scalars(
            select(Member)
            .join(BoardAttendance, BoardAttendance.member_id == Member.id)
            .where(BoardAttendance.meeting_id == m.id)
        )
    ]
    present.sort(key=str.lower)
    polls = {
        p.id: p
        for p in db.session.scalars(
            select(Poll).where(
                Poll.id.in_([i.poll_id for i in _items(m.id) if i.poll_id])
            )
        )
    }
    data = pdf.minutes(m, _items(m.id), present, polls, member.language)
    return _pdf_response(
        data, f"protokoll-{_slug(m.title)}.pdf", request.args.get("inline") == "1"
    )
