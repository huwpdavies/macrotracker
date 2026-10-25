import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Food, Tag


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        fruit = Tag(name="Fruit")
        db.session.add_all([fruit, Food(name="Apple", unit="unit", basis_amount=1, serving_size=1, tags=[fruit])])
        db.session.commit()
        yield app.test_client()


def test_manage_page_lists_tags_with_counts(client):
    html = client.get("/tags/").data.decode()
    assert 'value="Fruit"' in html and "1 food" in html


def test_add_rename_and_delete_a_tag(client):
    client.post("/tags/", data={"name": "  Breakfast  "})
    assert Tag.query.filter_by(name="Breakfast").one()
    resp = client.post("/tags/1/rename", data={"name": "Fresh fruit"}, follow_redirects=True)
    assert b"Renamed Fruit to Fresh fruit" in resp.data
    client.post("/tags/1/delete")
    assert db.session.get(Tag, 1) is None
    assert Food.query.one().tags == []          # the food stays, only the tag goes


def test_tag_names_are_unique_ignoring_case(client):
    resp = client.post("/tags/", data={"name": "fruit"}, follow_redirects=True)
    assert b"already a tag called fruit" in resp.data and Tag.query.count() == 1
