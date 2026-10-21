import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Food

FORM = {"name": "Tesco tuna 105g can", "unit": "g", "basis_amount": "100", "calories_kcal": "110", "protein_g": "25",
        "carbs_g": "0", "fat_g": "1", "salt_g": "1", "fibre_g": "0", "serving_size": "105",
        "serving_label": "1 can"}


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app.test_client()


def test_create_food_and_see_per_serving(client):
    resp = client.post("/foods/new", data=FORM, follow_redirects=True)
    assert resp.status_code == 200
    assert b'<span class="tile-value">26.3</span>' in resp.data  # 26.25 g protein per can, rounded for display
    assert Food.query.count() == 1


def test_validation_error_redisplays_form(client):
    resp = client.post("/foods/new", data={**FORM, "name": ""})
    assert resp.status_code == 200
    assert b"This field is required" in resp.data
    assert Food.query.count() == 0


def test_edit_and_delete(client):
    client.post("/foods/new", data=FORM)
    client.post("/foods/1/edit", data={**FORM, "name": "Tuna v2"})
    assert db.session.get(Food, 1).name == "Tuna v2"
    client.post("/foods/1/delete")
    assert Food.query.count() == 0


def test_search_returns_fragment_for_htmx(client):
    client.post("/foods/new", data=FORM)
    client.post("/foods/new", data={**FORM, "name": "Avocado"})
    resp = client.get("/foods/?q=avo", headers={"HX-Request": "true"})
    assert b"Avocado" in resp.data and b"tuna" not in resp.data
    assert b"<html" not in resp.data


def test_preview_fragment(client):
    resp = client.post("/foods/preview", data=FORM)
    assert b'<span class="tile-value">26.3</span>' in resp.data


def test_favourite_toggle_and_sort(client):
    client.post("/foods/new", data={**FORM, "name": "Apple"})
    client.post("/foods/new", data={**FORM, "name": "Zucchini"})
    resp = client.post("/foods/2/favourite", data={"q": ""})
    assert resp.data.index(b"Zucchini") < resp.data.index(b"Apple")
    assert db.session.get(Food, 2).is_favourite is True


def test_parse_label_endpoint(client):
    text = "Per 100g\nEnergy 1046kJ / 250kcal\nFat 10g\nCarbohydrate 5g\nProtein 30g\nSalt 1.2g"
    resp = client.post("/foods/parse-label", json={"text": text})
    assert resp.json["values"]["calories_kcal"] == 250
    assert resp.json["values"]["salt_g"] == 1.2
    assert resp.json["missing"] == ["fibre_g"]
