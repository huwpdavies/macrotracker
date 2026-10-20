from macrotracker import create_app


def test_home_page_says_hello():
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Hello, Macro Tracker" in resp.data
    assert b'name="robots" content="noindex"' in resp.data


def test_robots_txt_disallows_all():
    resp = create_app().test_client().get("/robots.txt")
    assert b"Disallow: /" in resp.data


def test_css_is_served_from_public():
    assert create_app().test_client().get("/css/main.css").status_code == 200
