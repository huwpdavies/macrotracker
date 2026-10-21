from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Goal, LogEntry
from macrotracker.services import dashboard

DAY = date(2026, 10, 21)
GOAL = SimpleNamespace(calories_kcal=2000, protein_g=100, carbs_g=200, fat_g=70, fibre_g=30, salt_g=6)


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()


def entry(day=DAY, **values):
    nutrients = {"calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fibre_g": 0, "salt_g": 0, **values}
    return LogEntry(log_date=day, description="x", quantity=1, unit="g", **nutrients)


def test_day_totals_are_summed_by_the_database_and_ignore_other_days(client):
    db.session.add_all([entry(protein_g=10, calories_kcal=100), entry(protein_g=5.5, calories_kcal=50),
                        entry(day=date(2026, 10, 20), protein_g=99)])
    db.session.commit()
    totals = dashboard.day_totals(DAY)
    assert totals["protein_g"] == Decimal("15.5") and totals["calories_kcal"] == 150


def test_empty_day_totals_are_zero(client):
    assert dashboard.day_totals(DAY) == {k: 0 for k in dashboard.NUTRIENTS}


def by_key(totals):
    return {r["key"]: r for r in dashboard.progress(totals, GOAL)}


def test_status_under_on_and_over():
    rows = by_key({"calories_kcal": Decimal(1000), "protein_g": Decimal(95), "carbs_g": Decimal(250),
                   "fat_g": Decimal(70), "fibre_g": Decimal(40), "salt_g": Decimal(8)})
    assert rows["calories_kcal"]["status"] == "under" and rows["calories_kcal"]["remaining"] == 1000
    assert rows["protein_g"]["status"] == "on"            # 95% is within 90-110
    assert rows["carbs_g"]["tone"] == "warn"              # 125%: too much
    assert rows["salt_g"]["tone"] == "warn"               # salt over is a warning
    assert rows["fibre_g"]["tone"] == "celebrate"         # fibre over is a win
    assert rows["fat_g"]["percent"] == 100


def test_no_goal_means_no_targets():
    rows = dashboard.progress({k: Decimal(10) for k in dashboard.NUTRIENTS}, None)
    assert all(r["status"] == "no-target" and r["percent"] is None for r in rows)


def test_dashboard_page_compares_day_with_active_goal(client):
    db.session.add(Goal(name="Maintain", is_active=True, calories_kcal=2000, protein_g=100,
                        carbs_g=200, fat_g=70, fibre_g=30, salt_g=6))
    db.session.add(entry(calories_kcal=500, protein_g=120, salt_g=7))
    db.session.commit()
    html = client.get("/?day=2026-10-21").data
    assert b"Maintain" in html
    assert b"1500 kcal to go" in html
    assert b"Goal reached, 20 g extra" in html   # protein 120 / 100
    assert b"1 g over" in html                    # salt 7 / 6
    assert b"25%" in html                         # calories 500 / 2000


def test_dashboard_without_goal_invites_one(client):
    html = client.get("/").data
    assert b"Set a goal" in html and b"Your plate is empty today" in html


def test_bad_day_in_query_string_is_404(client):
    assert client.get("/?day=31-02-2026").status_code == 404


def test_salt_is_a_ceiling_so_just_over_100_percent_warns():
    rows = by_key({**{k: Decimal(0) for k in dashboard.NUTRIENTS}, "salt_g": Decimal("6.3")})
    assert rows["salt_g"]["status"] == "over" and rows["salt_g"]["tone"] == "warn"   # 105%
    rows = by_key({**{k: Decimal(0) for k in dashboard.NUTRIENTS}, "salt_g": Decimal("5.7")})
    assert rows["salt_g"]["status"] == "on"                                          # 95%
