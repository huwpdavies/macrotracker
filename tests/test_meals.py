import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Food, Meal, MealItem


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        db.session.add_all([
            Food(name="Tuna", unit="g", basis_amount=100, calories_kcal=110, protein_g=25,
                 carbs_g=0, fat_g=1, salt_g=1, fibre_g=0, serving_size=105),
            Food(name="Avocado", unit="unit", basis_amount=1, calories_kcal=250, protein_g=2,
                 carbs_g=12, fat_g=22, salt_g=0, fibre_g=10, serving_size=0.5),
        ])
        db.session.commit()
        yield app.test_client()


def meal_data(**extra):
    data = {"name": "Lunch", "servings": "1",
            "item_food_id": ["1", "2"], "item_amount": ["1", "0.5"], "item_mode": ["servings", "amount"]}
    data.update(extra)
    return data


def test_create_meal_converts_servings_and_amounts(client):
    resp = client.post("/meals/new", data=meal_data(), follow_redirects=True)
    assert resp.status_code == 200
    items = {i.food_id: i.quantity for i in MealItem.query.all()}
    assert items[1] == 105          # 1 serving of tuna = 105 g
    assert items[2] == 0.5          # raw amount: half an avocado
    assert b'<span class="tile-value">241</span>' in resp.data  # 115.5 + 125 = 240.5 kcal, rounded half-up


def test_per_serving_uses_recipe_servings(client):
    resp = client.post("/meals/new", data=meal_data(servings="2"), follow_redirects=True)
    assert b"1 of 2" in resp.data
    assert b'<span class="tile-value">120</span>' in resp.data  # 240.5 / 2 = 120.25 kcal


def test_meal_needs_an_ingredient(client):
    resp = client.post("/meals/new", data=meal_data(item_food_id=[""], item_amount=["1"], item_mode=["servings"]))
    assert b"Add at least one ingredient" in resp.data
    assert Meal.query.count() == 0


def test_edit_replaces_items(client):
    client.post("/meals/new", data=meal_data())
    client.post("/meals/1/edit", data=meal_data(item_food_id=["2"], item_amount=["1"], item_mode=["amount"]))
    assert [(i.food_id, i.quantity) for i in MealItem.query.all()] == [(2, 1)]


def test_edit_form_shows_existing_items(client):
    client.post("/meals/new", data=meal_data())
    resp = client.get("/meals/1/edit")
    assert resp.data.count(b'class="item-row"') == 2


def test_delete_meal_removes_items(client):
    client.post("/meals/new", data=meal_data())
    client.post("/meals/1/delete")
    assert Meal.query.count() == 0 and MealItem.query.count() == 0


def test_food_in_a_meal_cannot_be_deleted(client):
    client.post("/meals/new", data=meal_data())
    resp = client.post("/foods/1/delete", follow_redirects=True)
    assert b"used in a meal" in resp.data
    assert db.session.get(Food, 1) is not None


def test_row_and_preview_fragments(client):
    assert b'name="item_food_id"' in client.get("/meals/row").data
    resp = client.post("/meals/preview", data=meal_data())
    assert b"Whole recipe" in resp.data and b"<html" not in resp.data


def test_favourite_sorts_first(client):
    client.post("/meals/new", data=meal_data(name="Apple pie"))
    client.post("/meals/new", data=meal_data(name="Zebra stew"))
    resp = client.post("/meals/2/favourite", headers={"HX-Request": "true"})
    assert resp.data.index(b"Zebra") < resp.data.index(b"Apple")
