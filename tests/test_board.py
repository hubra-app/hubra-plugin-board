"""The board plugin: tasks per function, year planner, contracts, the GV.

Runs with Hubra's fixtures once the plugin is in plugins/board of a Hubra
checkout (see README.md).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

BASE = "/api/v1/app/board"
READ = ["board.tasks.read"]


@pytest.fixture
def club(client, app, db, seeded_db):
    """Admin, Kassierin Kim (holds the function Kassier, may read tasks),
    Max (an ordinary member) and the function Kassier."""
    from hubra.core.models.function import Function, FunctionHolder

    set_modules(True, "board")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    kim = _make_role_and_member(db, tier, name="Kim", permission_keys=READ)
    max_ = _make_role_and_member(db, tier, name="Max")
    kassier = Function(name="Kassier")
    db.session.add(kassier)
    db.session.flush()
    db.session.add(FunctionHolder(function_id=kassier.id, member_id=kim.id))
    db.session.commit()
    _login(client, "admin@test.ch")
    return {"kim": kim.id, "max": max_.id, "kassier": kassier.id}


def _bell(db, member_id):
    from hubra.core.models.notification import Notification

    return [
        n.title
        for n in db.session.scalars(
            select(Notification).where(Notification.member_id == member_id)
        )
    ]


# ── Dates ────────────────────────────────────────────────────────────────────


def test_notice_deadline_rolls_with_renewals(app):
    from hubra_board.models import BoardContract
    from hubra_board.services import add_months, current_end, notice_deadline

    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    c = BoardContract(
        title="Haftpflicht",
        ends_on=date(2025, 12, 31),
        notice_months=3,
        renews_months=12,
        ended=False,
    )
    today = date(2026, 5, 1)
    assert current_end(c, today) == date(2026, 12, 31)
    assert notice_deadline(c, today) == date(2026, 9, 30)
    # Too late for this term: the next term's deadline.
    assert notice_deadline(c, date(2026, 10, 1)) == date(2027, 9, 30)
    c.renews_months = 0
    assert current_end(c, today) == date(2025, 12, 31)
    assert notice_deadline(c, today) is None
    c.ended = True
    assert notice_deadline(c, today) is None


# ── Tasks ────────────────────────────────────────────────────────────────────


def test_a_function_task_follows_the_holder(client, db, club):
    from hubra.core.models.function import FunctionHolder

    r = client.post(
        f"{BASE}/tasks",
        json={
            "title": "Revisoren anfragen",
            "functionId": club["kassier"],
            "dueOn": "2026-02-01",
        },
    )
    assert r.status_code == 201, r.get_json()
    task = r.get_json()
    assert task["functionName"] == "Kassier" and task["ownerId"] is None

    _login(client, "kim@test.ch")
    mine = client.get(f"{BASE}/tasks?show=mine").get_json()
    assert [t["title"] for t in mine] == ["Revisoren anfragen"]
    # Kim may only read tasks, but closes her own.
    assert client.post(f"{BASE}/tasks", json={"title": "x"}).status_code == 403
    assert (
        client.patch(f"{BASE}/tasks/{task['id']}", json={"title": "y"}).status_code
        == 403
    )
    r = client.post(f"{BASE}/tasks/{task['id']}/done", json={"done": True})
    assert r.status_code == 200 and r.get_json()["done"]

    # The function changes hands: the task is Max's now.
    db.session.execute(
        FunctionHolder.__table__.update()
        .where(FunctionHolder.function_id == club["kassier"])
        .values(member_id=club["max"])
    )
    db.session.commit()
    r = client.post(f"{BASE}/tasks/{task['id']}/done", json={"done": False})
    assert r.status_code == 403


def test_a_task_for_someone_tells_them(client, db, club):
    r = client.post(
        f"{BASE}/tasks", json={"title": "Schlüssel abgeben", "ownerId": club["max"]}
    )
    assert r.status_code == 201
    assert "Neue Aufgabe für dich" in _bell(db, club["max"])
    assert client.post(f"{BASE}/tasks", json={"title": " "}).status_code == 400
    assert (
        client.post(f"{BASE}/tasks", json={"title": "x", "ownerId": 999999}).status_code
        == 400
    )


def test_members_without_the_right_see_no_tasks(client, club):
    _login(client, "max@test.ch")
    assert client.get(f"{BASE}/tasks").status_code == 403
    assert client.get(f"{BASE}/contracts").status_code == 403


# ── Reminders ────────────────────────────────────────────────────────────────


def test_the_planner_makes_one_task_a_year(client, db, club):
    from hubra_board import services
    from hubra_board.models import BoardTask

    r = client.post(
        f"{BASE}/duties",
        json={
            "title": "SUISA melden",
            "month": 3,
            "day": 31,
            "functionId": club["kassier"],
            "remindDays": 14,
        },
    )
    assert r.status_code == 201
    assert services.remind(date(2026, 3, 1))["duties"] == 0
    assert services.remind(date(2026, 3, 20))["duties"] == 1
    assert services.remind(date(2026, 3, 21))["duties"] == 0
    db.session.commit()
    tasks = list(db.session.scalars(select(BoardTask)))
    assert [(t.title, t.due_on) for t in tasks] == [("SUISA melden", date(2026, 3, 31))]
    assert "Jahresplan: SUISA melden" in _bell(db, club["kim"])
    # Next year again.
    assert services.remind(date(2027, 3, 18))["duties"] == 1


def test_due_tasks_and_notice_deadlines_are_reminded_once(client, db, club):
    from hubra_board import services

    client.post(
        f"{BASE}/tasks",
        json={"title": "Budget", "ownerId": club["kim"], "dueOn": "2026-04-03"},
    )
    r = client.post(
        f"{BASE}/contracts",
        json={
            "title": "Miete Clublokal",
            "kind": "rent",
            "party": "Gemeinde",
            "cost": "1200.50",
            "endsOn": "2026-06-30",
            "noticeMonths": 3,
            "renewsMonths": 12,
            "remindDays": 30,
            "functionId": club["kassier"],
        },
    )
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["cost"] == 1200.5
    assert services.remind(date(2026, 3, 1)) == {
        "duties": 0,
        "tasks": 0,
        "contracts": 1,
        "meetings": 0,
    }
    assert services.remind(date(2026, 4, 1))["tasks"] == 1
    assert services.remind(date(2026, 4, 2)) == {
        "duties": 0,
        "tasks": 0,
        "contracts": 0,
        "meetings": 0,
    }
    db.session.commit()
    bell = _bell(db, club["kim"])
    assert "Kündigungsfrist: Miete Clublokal" in bell
    assert "Aufgabe bald fällig: Budget" in bell
    listed = client.get(f"{BASE}/contracts").get_json()
    assert listed[0]["noticeBy"] is not None


def test_bad_contract_values_are_refused(client, club):
    for body in (
        {"title": "x", "kind": "boat"},
        {"title": "x", "cost": "abc"},
        {"title": "x", "startsOn": "2026-05-01", "endsOn": "2026-01-01"},
        {"title": "x", "noticeMonths": 99},
    ):
        assert client.post(f"{BASE}/contracts", json=body).status_code == 400, body


# ── General meeting ──────────────────────────────────────────────────────────


def _gv(client, **extra):
    starts = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0)
    r = client.post(
        f"{BASE}/meetings",
        json={
            "title": "GV 2026",
            "startsAt": starts.isoformat(),
            "place": "Clublokal",
            "quorum": 2,
            "standardAgenda": True,
            **extra,
        },
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_the_gv_from_invitation_to_minutes(client, db, club):
    gv = _gv(client)
    assert len(gv["agenda"]) == 9 and gv["agenda"][0]["title"].startswith("Begrüssung")

    # Members don't see it before the invitation.
    _login(client, "max@test.ch")
    assert client.get(f"{BASE}/meetings").get_json() == []
    assert client.get(f"{BASE}/meetings/{gv['id']}").status_code == 404
    _login(client, "admin@test.ch")

    r = client.post(
        f"{BASE}/meetings/{gv['id']}/agenda", json={"title": "Statutenänderung"}
    )
    assert len(r.get_json()["agenda"]) == 10
    ids = [i["id"] for i in r.get_json()["agenda"]]
    r = client.put(f"{BASE}/meetings/{gv['id']}/agenda/order", json={"ids": ids[::-1]})
    assert r.get_json()["agenda"][0]["title"] == "Statutenänderung"
    assert (
        client.put(
            f"{BASE}/meetings/{gv['id']}/agenda/order", json={"ids": ids[:2]}
        ).status_code
        == 400
    )

    r = client.post(f"{BASE}/meetings/{gv['id']}/invite")
    assert r.status_code == 200 and r.get_json()["sent"] >= 3
    assert client.post(f"{BASE}/meetings/{gv['id']}/invite").status_code == 409
    assert "Einladung: GV 2026" in _bell(db, club["max"])

    _login(client, "max@test.ch")
    seen = client.get(f"{BASE}/meetings/{gv['id']}").get_json()
    assert seen["canManage"] is False and len(seen["agenda"]) == 10
    pdf = client.get(f"{BASE}/meetings/{gv['id']}/invitation.pdf")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    # Minutes only once the meeting is closed.
    assert client.get(f"{BASE}/meetings/{gv['id']}/minutes.pdf").status_code == 404
    assert (
        client.put(f"{BASE}/meetings/{gv['id']}/attendance/{club['max']}").status_code
        == 403
    )

    _login(client, "admin@test.ch")
    r = client.put(f"{BASE}/meetings/{gv['id']}/attendance/{club['max']}")
    assert r.get_json() == {"present": 1, "quorate": False}
    r = client.put(f"{BASE}/meetings/{gv['id']}/attendance/{club['kim']}")
    assert r.get_json() == {"present": 2, "quorate": True}
    listed = client.get(f"{BASE}/meetings/{gv['id']}/attendance").get_json()
    assert listed["present"] == 2 and sum(m["present"] for m in listed["members"]) == 2

    item = seen["agenda"][3]["id"]
    r = client.patch(
        f"{BASE}/agenda/{item}",
        json={
            "minutes": "Der Kassier stellt die Rechnung vor.",
            "decision": "Einstimmig genehmigt",
        },
    )
    assert r.status_code == 200
    r = client.post(f"{BASE}/meetings/{gv['id']}/close")
    assert r.get_json()["closedAt"]
    assert (
        client.put(f"{BASE}/meetings/{gv['id']}/attendance/{club['max']}").status_code
        == 409
    )

    _login(client, "max@test.ch")
    pdf = client.get(f"{BASE}/meetings/{gv['id']}/minutes.pdf")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"


def test_an_invitation_needs_an_agenda(client, club):
    gv = _gv(client, standardAgenda=False)
    r = client.post(f"{BASE}/meetings/{gv['id']}/invite")
    assert r.status_code == 409 and r.get_json()["error"] == "NO_AGENDA"


def test_the_board_hears_before_the_invitation_deadline(client, db, club):
    from hubra_board import services

    gv = _gv(client)  # in 30 days, invitation 20 days before: in 10 days
    today = datetime.now(timezone.utc).date()
    assert services.remind(today)["meetings"] == 0
    assert services.remind(today + timedelta(days=4))["meetings"] == 1
    assert services.remind(today + timedelta(days=5))["meetings"] == 0
    db.session.commit()
    admin_id = client.get(f"{BASE}/options").get_json()["memberId"]
    assert "Einladung verschicken: GV 2026" in _bell(db, admin_id)
    assert gv["inviteBy"] == (today + timedelta(days=10)).isoformat()


def test_module_off_hides_the_api(client, club):
    set_modules(False, "board")
    r = client.get(f"{BASE}/tasks")
    assert r.status_code == 403 and r.get_json()["error"] == "MODULE_DISABLED"


def test_the_plugin_loads_within_its_limits(app):
    from hubra.core.plugins import loader

    with app.app_context():
        spec = loader.current().get("board")
    assert spec is not None and spec.loaded, spec and spec.error
    assert spec.manifest.get("uses") is not None
