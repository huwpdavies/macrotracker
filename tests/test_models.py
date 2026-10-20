import pytest
from sqlalchemy.exc import IntegrityError

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Goal


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app


def _goal(name, active):
    return Goal(name=name, protein_g=1, carbs_g=1, fat_g=1, salt_g=1, fibre_g=1, is_active=active)


def test_only_one_active_goal_allowed(app):
    db.session.add(_goal("A", True))
    db.session.commit()
    db.session.add(_goal("B", True))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_many_inactive_goals_allowed(app):
    db.session.add_all([_goal("A", False), _goal("B", False)])
    db.session.commit()
    assert Goal.query.count() == 2


def test_seed_runs_once(app):
    runner = app.test_cli_runner()
    assert "Seeded" in runner.invoke(args=["seed"]).output
    assert "nothing seeded" in runner.invoke(args=["seed"]).output
