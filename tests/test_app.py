from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db


def _app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    return app


def test_home_page_says_hello():
    client = _app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Hello, Macro Tracker" in resp.data
    assert b'name="robots" content="noindex"' in resp.data


def test_robots_txt_disallows_all():
    resp = _app().test_client().get("/robots.txt")
    assert b"Disallow: /" in resp.data


def test_css_is_served_from_public():
    assert _app().test_client().get("/css/main.css").status_code == 200
