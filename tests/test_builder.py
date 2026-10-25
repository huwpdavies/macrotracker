from decimal import Decimal

import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Food, FoodIngredient, Tag
from macrotracker.services import recipes

PLAIN = {"name": "Tuna", "unit": "g", "basis_amount": "100", "calories_kcal": "110", "protein_g": "25",
         "carbs_g": "0", "fat_g": "1", "salt_g": "1", "fibre_g": "0", "serving_size": "105", "serving_label": "1 can"}


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        recipes.ensure_default_tags()
        db.session.add_all([
            Food(name="Tuna", unit="g", basis_amount=100, calories_kcal=110, protein_g=25,
                 carbs_g=0, fat_g=1, salt_g=1, fibre_g=0, serving_size=105),
            Food(name="Avocado", unit="unit", basis_amount=1, calories_kcal=250, protein_g=2,
                 carbs_g=12, fat_g=22, salt_g=0, fibre_g=10, serving_size=0.5),
        ])
        db.session.commit()
        yield app.test_client()


def meal_tag_id():
    return str(Tag.query.filter_by(name="Meal").one().id)


def build_data(**extra):
    data = {"name": "Lunch", "recipe_servings": "1", "item_key": ["a", "b"], "tag_ids": [meal_tag_id()],
            "item_food": ["Tuna", "Avocado"], "item_amount": ["1", "0.5"], "item_mode": ["servings", "amount"]}
    data.update(extra)
    return data


def built(name):
    return Food.query.filter_by(name=name).one()


def test_add_food_page_offers_both_ways(client):
    for url in ("/foods/new", "/foods/build"):
        html = client.get(url).data.decode()
        assert "Add a new food" in html and "Build from ingredients" in html


def test_build_page_starts_with_meal_ticked(client):
    html = client.get("/foods/build").data.decode()
    assert f'name="tag_ids" value="{meal_tag_id()}" checked' in html


def test_build_a_food_from_ingredients(client):
    resp = client.post("/foods/build", data=build_data(recipe_servings="2"), follow_redirects=True)
    lunch = built("Lunch")
    assert lunch.is_built and lunch.unit == "serving" and lunch.recipe_servings == 2
    assert [(i.ingredient.name, i.quantity) for i in lunch.ingredients] == [("Tuna", 105), ("Avocado", Decimal("0.5"))]
    assert lunch.calories_kcal == Decimal("120.25")      # (115.5 + 125) / 2, stored per serving
    assert [t.name for t in lunch.tags] == ["Meal"]
    assert b"1 of 2" in resp.data and b"Ingredients" in resp.data


def test_meal_tag_can_be_left_off(client):
    client.post("/foods/build", data=build_data(tag_ids=[]))
    assert built("Lunch").tags == []


def test_new_tags_can_be_typed_on_the_form(client):
    client.post("/foods/new", data={**PLAIN, "name": "Tuna 2", "new_tags": "Fish, meat, Fish"})
    assert sorted(t.name for t in built("Tuna 2").tags) == ["Fish", "Meat"]   # "meat" matched the existing tag


def test_editing_an_ingredient_updates_built_foods_that_use_it_even_nested(client):
    client.post("/foods/build", data=build_data())                                       # Lunch: tuna + avocado
    client.post("/foods/build", data=build_data(name="Big day", item_key=["c"], item_food=["Lunch"],
                                                 item_amount=["2"], item_mode=["servings"]))  # 2 x Lunch
    assert built("Big day").calories_kcal == Decimal("481")
    resp = client.post("/foods/1/edit", data={**PLAIN, "calories_kcal": "210"}, follow_redirects=True)
    assert built("Lunch").calories_kcal == Decimal("345.5")        # 220.5 + 125
    assert built("Big day").calories_kcal == Decimal("691")        # 2 x 345.5
    assert b"Updated 2 built foods" in resp.data


def test_a_food_cannot_contain_itself_even_indirectly(client):
    client.post("/foods/build", data=build_data())
    client.post("/foods/build", data=build_data(name="Big day", item_key=["c"], item_food=["Lunch"],
                                                 item_amount=["1"], item_mode=["servings"]))
    lunch_id = built("Lunch").id
    resp = client.post(f"/foods/{lunch_id}/edit", data=build_data(item_key=["a", "c"], item_food=["Tuna", "Big day"],
                                                               item_amount=["1", "1"], item_mode=["servings", "servings"]))
    assert b"Big day already contains Lunch" in resp.data
    assert [i.ingredient.name for i in built("Lunch").ingredients] == ["Tuna", "Avocado"]


def test_an_ingredient_cannot_be_deleted_while_used(client):
    client.post("/foods/build", data=build_data())
    resp = client.post("/foods/1/delete", follow_redirects=True)
    assert b"Tuna is an ingredient in Lunch" in resp.data and db.session.get(Food, 1)


def test_deleting_a_built_food_removes_its_lines_not_its_ingredients(client):
    client.post("/foods/build", data=build_data())
    client.post(f"/foods/{built('Lunch').id}/delete")
    assert FoodIngredient.query.count() == 0 and Food.query.count() == 2


def test_unknown_ingredient_is_rejected(client):
    resp = client.post("/foods/build", data=build_data(item_food=["Tuna", "Unicorn"]))
    assert b"Couldn&#39;t find &#39;Unicorn&#39;" in resp.data and Food.query.count() == 2


def test_build_preview_updates_totals_and_each_line(client):
    html = client.post("/foods/build-preview", data=build_data()).data.decode()
    assert 'id="m-a" hx-swap-oob="true"' in html and "P&nbsp;26.3" in html and "0.5&nbsp;unit" in html


def test_food_list_filters_by_tag(client):
    client.post("/foods/build", data=build_data())
    html = client.get("/foods/?tag=Meal").data.decode()
    assert "Lunch" in html and ">Tuna<" not in html
