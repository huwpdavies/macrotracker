import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Goal
from macrotracker.services import goals as goal_service

FORM = {"name": "Maintain", "calories_kcal": "2200", "protein_g": "130", "carbs_g": "250",
        "fat_g": "70", "fibre_g": "30", "salt_g": "6"}


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()


def active_names():
    return [g.name for g in Goal.query.filter_by(is_active=True)]


def test_first_goal_becomes_active_and_later_ones_do_not(client):
    client.post("/goals/new", data=FORM)
    client.post("/goals/new", data={**FORM, "name": "Cut"})
    assert active_names() == ["Maintain"]


def test_activate_switches_in_one_click(client):
    for name in ("A", "B", "C"):
        client.post("/goals/new", data={**FORM, "name": name})
    client.post("/goals/3/activate")
    assert active_names() == ["C"]
    client.post("/goals/2/activate")
    assert active_names() == ["B"]


def test_deleting_active_goal_asks_for_replacement(client):
    client.post("/goals/new", data={**FORM, "name": "A"})
    client.post("/goals/new", data={**FORM, "name": "B"})
    resp = client.post("/goals/1/delete")
    assert b"Which goal should take over?" in resp.data
    assert Goal.query.count() == 2


def test_delete_active_with_replacement_switches_and_deletes(client):
    client.post("/goals/new", data={**FORM, "name": "A"})
    client.post("/goals/new", data={**FORM, "name": "B"})
    client.post("/goals/1/delete", data={"replacement_id": "2"})
    assert [g.name for g in Goal.query.all()] == ["B"]
    assert active_names() == ["B"]


def test_inactive_goal_and_only_goal_can_be_deleted(client):
    client.post("/goals/new", data={**FORM, "name": "A"})
    client.post("/goals/new", data={**FORM, "name": "B"})
    client.post("/goals/2/delete")
    client.post("/goals/1/delete")
    assert Goal.query.count() == 0


def test_activate_rolls_back_if_something_fails(client, monkeypatch):
    client.post("/goals/new", data={**FORM, "name": "A"})
    client.post("/goals/new", data={**FORM, "name": "B"})

    def boom():
        raise RuntimeError("database went away")

    monkeypatch.setattr(db.session, "commit", boom)
    with pytest.raises(RuntimeError):
        goal_service.activate(db.session.get(Goal, 2))
    monkeypatch.undo()
    assert active_names() == ["A"]  # nothing half-done


def test_next_redirect_stays_on_site(client):
    client.post("/goals/new", data={**FORM, "name": "A"})
    client.post("/goals/new", data={**FORM, "name": "B"})
    resp = client.post("/goals/2/activate", data={"next": "https://evil.example"})
    assert resp.headers["Location"] == "/goals/"


def test_edit_goal(client):
    client.post("/goals/new", data=FORM)
    client.post("/goals/1/edit", data={**FORM, "protein_g": "150"})
    assert db.session.get(Goal, 1).protein_g == 150
