"""board tasks, duties, contracts, meetings, agenda items and attendance

Runs in public and in every club's schema, tracked in its own version table
(alembic_version_board). has_table() keeps it safe to run twice.

Revision ID: 5c2e8a4f1d73
Revises:
Create Date: 2026-11-05 10:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "5c2e8a4f1d73"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name, nullable=True):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _member(name):
    return sa.Column(name, sa.Integer(), nullable=True)


def upgrade():
    if not has_table("board_duties"):
        op.create_table(
            "board_duties",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("day", sa.Integer(), nullable=False),
            _member("owner_id"),
            sa.Column("function_id", sa.Integer(), nullable=True),
            sa.Column("remind_days", sa.Integer(), nullable=False),
            sa.Column("last_year", sa.Integer(), nullable=True),
            _ts("created_at", False),
            sa.ForeignKeyConstraint(["owner_id"], ["members.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["function_id"], ["functions.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not has_table("board_tasks"):
        op.create_table(
            "board_tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            _member("owner_id"),
            sa.Column("function_id", sa.Integer(), nullable=True),
            sa.Column("due_on", sa.Date(), nullable=True),
            _ts("done_at"),
            _member("done_by"),
            _ts("reminded_at"),
            sa.Column("duty_id", sa.Integer(), nullable=True),
            _member("created_by"),
            _ts("created_at", False),
            sa.ForeignKeyConstraint(["owner_id"], ["members.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["done_by"], ["members.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["created_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["function_id"], ["functions.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["duty_id"], ["board_duties.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_board_tasks_owner_id", "board_tasks", ["owner_id"])
        op.create_index("ix_board_tasks_function_id", "board_tasks", ["function_id"])
        op.create_index("ix_board_tasks_duty_id", "board_tasks", ["duty_id"])
    if not has_table("board_contracts"):
        op.create_table(
            "board_contracts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("party", sa.String(200), nullable=True),
            sa.Column("reference", sa.String(100), nullable=True),
            sa.Column("cost", sa.Numeric(12, 2), nullable=True),
            sa.Column("cost_period", sa.String(10), nullable=False),
            sa.Column("starts_on", sa.Date(), nullable=True),
            sa.Column("ends_on", sa.Date(), nullable=True),
            sa.Column("notice_months", sa.Integer(), nullable=False),
            sa.Column("renews_months", sa.Integer(), nullable=False),
            sa.Column("remind_days", sa.Integer(), nullable=False),
            _member("owner_id"),
            sa.Column("function_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("ended", sa.Boolean(), nullable=False),
            sa.Column("reminded_for", sa.Date(), nullable=True),
            _ts("created_at", False),
            sa.ForeignKeyConstraint(["owner_id"], ["members.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["function_id"], ["functions.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not has_table("board_meetings"):
        op.create_table(
            "board_meetings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            _ts("starts_at", False),
            sa.Column("place", sa.String(300), nullable=True),
            sa.Column("invite_days", sa.Integer(), nullable=False),
            sa.Column("quorum", sa.Integer(), nullable=False),
            sa.Column("intro", sa.Text(), nullable=True),
            sa.Column("chair", sa.String(200), nullable=True),
            sa.Column("minute_taker", sa.String(200), nullable=True),
            _ts("invited_at"),
            _ts("deadline_reminded_at"),
            _ts("closed_at"),
            _member("created_by"),
            _ts("created_at", False),
            sa.ForeignKeyConstraint(
                ["created_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not has_table("board_agenda_items"):
        op.create_table(
            "board_agenda_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_id", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("poll_id", sa.Integer(), nullable=True),
            sa.Column("minutes", sa.Text(), nullable=True),
            sa.Column("decision", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["meeting_id"], ["board_meetings.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_board_agenda_items_meeting_id", "board_agenda_items", ["meeting_id"]
        )
    if not has_table("board_attendance"):
        op.create_table(
            "board_attendance",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_id", sa.Integer(), nullable=False),
            sa.Column("member_id", sa.Integer(), nullable=False),
            _ts("signed_in_at", False),
            _member("signed_in_by"),
            sa.ForeignKeyConstraint(
                ["meeting_id"], ["board_meetings.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["signed_in_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("meeting_id", "member_id"),
        )
        op.create_index(
            "ix_board_attendance_meeting_id", "board_attendance", ["meeting_id"]
        )


def downgrade():
    for table in (
        "board_attendance",
        "board_agenda_items",
        "board_meetings",
        "board_contracts",
        "board_tasks",
        "board_duties",
    ):
        if has_table(table):
            op.drop_table(table)
