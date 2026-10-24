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
    data = {"name": "Lunch", "servings": "1", "item_key": ["a", "b"],
            "item_food": ["Tuna", "Avocado"], "item_amount": ["1", "0.5"], "item_mode": ["servings", "amount"]}
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
    resp = client.post("/meals/new", data=meal_data(item_key=["a"], item_food=[""], item_amount=["1"], item_mode=["servings"]))
    assert b"Add at least one ingredient" in resp.data
    assert Meal.query.count() == 0


def test_edit_replaces_items(client):
    client.post("/meals/new", data=meal_data())
    client.post("/meals/1/edit", data=meal_data(item_key=["a"], item_food=["Avocado"], item_amount=["1"], item_mode=["amount"]))
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
    assert b'name="item_food"' in client.get("/meals/row").data
    resp = client.post("/meals/preview", data=meal_data())
    assert b"Whole recipe" in resp.data and b"<html" not in resp.data


def test_favourite_sorts_first(client):
    client.post("/meals/new", data=meal_data(name="Apple pie"))
    client.post("/meals/new", data=meal_data(name="Zebra stew"))
    resp = client.post("/meals/2/favourite", headers={"HX-Request": "true"})
    assert resp.data.index(b"Zebra") < resp.data.index(b"Apple")



def test_food_search_matches_names_ignoring_case(client):
    client.post("/meals/new", data=meal_data(item_food=["tuna", "AVOCADO"]))
    assert [i.food_id for i in MealItem.query.order_by(MealItem.id)] == [1, 2]


def test_unknown_food_name_is_rejected_with_a_message(client):
    resp = client.post("/meals/new", data=meal_data(item_food=["Tuna", "Unicorn"]))
    assert b"Couldn&#39;t find &#39;Unicorn&#39;" in resp.data
    assert Meal.query.count() == 0


def test_duplicate_food_names_get_a_distinct_label(client):
    db.session.add(Food(name="Tuna", unit="unit", basis_amount=1, calories_kcal=1, protein_g=1,
                        carbs_g=0, fat_g=0, salt_g=0, fibre_g=0, serving_size=1))
    db.session.commit()
    html = client.get("/meals/new").data.decode()
    assert 'value="Tuna (g, #1)"' in html and 'value="Tuna (unit, #3)"' in html
    client.post("/meals/new", data=meal_data(item_key=["a"], item_food=["Tuna (unit, #3)"], item_amount=["2"], item_mode=["amount"]))
    assert MealItem.query.one().food_id == 3


def test_preview_updates_each_rows_macros_out_of_band(client):
    html = client.post("/meals/preview", data=meal_data()).data.decode()
    assert 'id="m-a" hx-swap-oob="true"' in html and 'id="m-b" hx-swap-oob="true"' in html
    assert "105&nbsp;g" in html and "P&nbsp;26.3" in html      # tuna row: 1 serving = 105 g
    assert "0.5&nbsp;unit" in html and "Fb&nbsp;5" in html     # avocado row


def test_meal_page_shows_totals_first_then_each_ingredients_macros(client):
    client.post("/meals/new", data=meal_data())
    html = client.get("/meals/1").data.decode()
    assert html.index("Totals") < html.index("Ingredients")
    table = html[html.index("ingredient-table"):]
    assert '<td class="num">26.3</td>' in table             # tuna protein
    assert '<td class="num kcal-col">125</td>' in table     # avocado calories
