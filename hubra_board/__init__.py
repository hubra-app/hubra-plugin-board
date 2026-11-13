"""Board (Vorstand): what the board runs between two general meetings.

- Tasks with a due date, for a person or for a function. A task for a
  function belongs to whoever holds it, so it passes to the next holder.
- The year planner: duties that come back every year (GV date, insurance,
  rent, SUISA, subsidies, audit), with a reminder some days before.
- Contracts and insurances with the other party, cost, end and notice
  period, and a reminder before the notice deadline.
- General meetings (GV): agenda (Traktanden), the invitation to every
  member before the deadline in the statutes, sign-in and quorum on the
  day, minutes per item and the minutes as a PDF.

Reminders go to the bell (topic "tasks") once a day.

Permissions:
    board.tasks.read          see tasks and the year planner
    board.tasks.update        add and change tasks and duties
    board.contracts.read      see contracts and insurances
    board.contracts.update    add and change them
    board.meetings.update     prepare and run general meetings

Dashboard widgets: open tasks (mine or all) and the next meetings.
"""

from hubra.core.contracts import WidgetField, widget_contract
from hubra.core.modules import Blueprint, Module, NavItem, Schedule

module = Module(
    code="board",
    # Access the standard roles get when a club first switches it on
    # (docs/roles.md in hubra-app/hubra).
    role_defaults={"board": "edit", "secretary": "all"},
    name="Board",
    description="Board tasks, year planner, contracts and the general meeting",
    default_enabled=False,
    depends_on=("members", "functions"),
    blueprints=(Blueprint("hubra_board.routes", "board_bp", "/api/v1/app/board"),),
    nav=(
        NavItem(
            "/app/board",
            "shell.nav.board",
            "briefcase",
            section="more",
            order=20,
            perms=("board.tasks.read",),
        ),
    ),
    tables=(
        "board_tasks",
        "board_duties",
        "board_contracts",
        "board_meetings",
        "board_agenda_items",
        "board_attendance",
    ),
    tasks=("hubra_board.tasks",),
    schedule=(Schedule("board-reminders-daily", "hubra_board.tasks.remind", 86400.0),),
    # The invitation and minutes PDFs on the club's letterhead (pdf.py).
    consumes={"pdf.render": ">=1,<2"},
    # Dashboard widgets (hubra_board/widgets.py).
    provides=(
        widget_contract(
            "board.tasks",
            "hubra_board.widgets:tasks",
            label="board.widget.tasks",
            description="board.widget.tasksHint",
            size="m",
            view="list",
            perm="board.tasks.read",
            fields=(
                WidgetField("mine", "board.widget.mine", "switch", True),
                WidgetField("count", "board.widget.count", "number", 5),
            ),
        ),
        widget_contract(
            "board.meetings",
            "hubra_board.widgets:meetings",
            label="board.widget.meetings",
            description="board.widget.meetingsHint",
            size="m",
            view="list",
            perm="board.tasks.read",
            fields=(WidgetField("count", "board.widget.count", "number", 3),),
        ),
    ),
)
