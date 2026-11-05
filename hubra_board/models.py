"""The board's tables (one copy per club schema)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _member_fk() -> ForeignKey:
    return ForeignKey("members.id", ondelete="SET NULL")


def _function_fk() -> ForeignKey:
    return ForeignKey("functions.id", ondelete="SET NULL")


class BoardTask(db.Model):
    """A to-do with a due date, for a member or for a function's holders."""

    __tablename__ = "board_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, _member_fk(), nullable=True, index=True
    )
    function_id: Mapped[int | None] = mapped_column(
        Integer, _function_fk(), nullable=True, index=True
    )
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    done_by: Mapped[int | None] = mapped_column(Integer, _member_fk(), nullable=True)
    # Set when the due-date reminder went out, so it goes once.
    reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # A task the year planner created for one year's duty.
    duty_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("board_duties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(Integer, _member_fk(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class BoardDuty(db.Model):
    """A duty that comes back every year on the same day (year planner)."""

    __tablename__ = "board_duties"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(Integer, _member_fk(), nullable=True)
    function_id: Mapped[int | None] = mapped_column(
        Integer, _function_fk(), nullable=True
    )
    # This many days before, the duty becomes a task and the holder is told.
    remind_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    # The last year a task was made for, so each year gets one.
    last_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class BoardContract(db.Model):
    """A contract or insurance: who with, what it costs, when it can end."""

    __tablename__ = "board_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # insurance | rent | licence | service | other
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    party: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # year | month | quarter | once
    cost_period: Mapped[str] = mapped_column(String(10), nullable=False, default="year")
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The end of the current term; empty for an open-ended contract.
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Renews by itself for this many months unless given notice (0: it ends).
    renews_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    remind_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    owner_id: Mapped[int | None] = mapped_column(Integer, _member_fk(), nullable=True)
    function_id: Mapped[int | None] = mapped_column(
        Integer, _function_fk(), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The notice deadline a reminder went out for.
    reminded_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class BoardMeeting(db.Model):
    """A general meeting (GV), ordinary or extraordinary."""

    __tablename__ = "board_meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    place: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # The statutes' deadline: the invitation goes out this many days before.
    invite_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    # Members who must be present for decisions (0: no quorum).
    quorum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    chair: Mapped[str | None] = mapped_column(String(200), nullable=True)
    minute_taker: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the board was told the invitation deadline is near.
    deadline_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, _member_fk(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class BoardAgendaItem(db.Model):
    """One item of a meeting's agenda (Traktandum), with its minutes."""

    __tablename__ = "board_agenda_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("board_meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A vote held as a club poll.
    poll_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("polls.id", ondelete="SET NULL"), nullable=True
    )
    minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)


class BoardAttendance(db.Model):
    """A member signed in at a meeting."""

    __tablename__ = "board_attendance"
    __table_args__ = (UniqueConstraint("meeting_id", "member_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("board_meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    signed_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    signed_in_by: Mapped[int | None] = mapped_column(
        Integer, _member_fk(), nullable=True
    )
