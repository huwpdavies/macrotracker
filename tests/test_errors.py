import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db


class BrokenDatabase(TestConfig):
    # A path that can't be opened: every query fails the way a Supabase outage would.
    SQLALCHEMY_DATABASE_URI = "sqlite:////no/such/folder/app.db"


def test_404_page_is_friendly():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        resp = app.test_client().get("/foods/999")
    assert resp.status_code == 404
    assert b"Page not found" in resp.data and b"Go to dashboard" in resp.data


def test_database_down_shows_503_page_not_a_crash():
    resp = create_app(BrokenDatabase).test_client().get("/foods/")
    assert resp.status_code == 503
    assert b"Can&#39;t reach your data" in resp.data and b"Try again" in resp.data


def test_unexpected_error_shows_500_page():
    app = create_app(TestConfig)
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("bug")

    resp = app.test_client().get("/boom")
    assert resp.status_code == 500 and b"Something went wrong" in resp.data


def test_deployed_app_refuses_to_start_without_a_secret_key(monkeypatch):
    from macrotracker import config
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config._secret_key()
    monkeypatch.setenv("SECRET_KEY", "a-real-key")
    assert config._secret_key() == "a-real-key"
