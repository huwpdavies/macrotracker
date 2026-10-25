import re
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from macrotracker import create_app
from macrotracker.config import TestConfig
from macrotracker.extensions import db
from macrotracker.models import Food, FoodIngredient, LogEntry, Tag
from macrotracker.services import dates, recipes

DAY = "2026-10-21"


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        tuna = Food(name="Tuna", unit="g", basis_amount=100, calories_kcal=110, protein_g=25,
                    carbs_g=0, fat_g=1, salt_g=1, fibre_g=0, serving_size=105, is_favourite=True)
        avocado = Food(name="Avocado", unit="unit", basis_amount=1, calories_kcal=250, protein_g=2,
                       carbs_g=12, fat_g=22, salt_g=0, fibre_g=10, serving_size=0.5)
        db.session.add_all([tuna, avocado])
        db.session.flush()
        lunch = Food(name="Lunch", recipe_servings=2, tags=[Tag(name="Meal")],
                     ingredients=[FoodIngredient(ingredient=tuna, quantity=210),
                                  FoodIngredient(ingredient=avocado, quantity=1)])
        recipes.apply_totals(lunch)   # one serving = 240.5 kcal, 27.25 g protein
        db.session.add(lunch)
        db.session.commit()
        yield app.test_client()


def add(client, **data):
    return client.post(f"/log/{DAY}/add", data=data, follow_redirects=True)


def test_today_uses_london_not_utc():
    # 23:30 UTC on 30 June is 00:30 on 1 July in London (BST).
    assert dates.today_london(datetime(2026, 6, 30, 23, 30, tzinfo=timezone.utc)) == date(2026, 7, 1)
    # In winter London is on UTC, so the dates agree.
    assert dates.today_london(datetime(2026, 12, 1, 23, 30, tzinfo=timezone.utc)) == date(2026, 12, 1)


def test_log_redirects_to_today(client):
    resp = client.get("/log/")
    assert resp.headers["Location"] == f"/log/{dates.today_london().isoformat()}"


def test_bad_date_is_404(client):
    assert client.get("/log/not-a-date").status_code == 404


def test_avocado_one_serving_adds_half_the_per_unit_macros(client):
    add(client, item_id="2", amount="1", mode="servings")
    entry = LogEntry.query.one()
    assert entry.quantity == Decimal("0.5")
    assert entry.fat_g == 11 and entry.calories_kcal == 125
    assert entry.log_date == date(2026, 10, 21)


def test_raw_amount_in_food_unit(client):
    add(client, item_id="1", amount="50", mode="amount")
    assert LogEntry.query.one().protein_g == Decimal("12.5")


def test_editing_a_food_does_not_change_logged_entries(client):
    add(client, item_id="1", amount="1", mode="servings")
    tuna = db.session.get(Food, 1)
    tuna.protein_g = 99
    db.session.commit()
    assert LogEntry.query.one().protein_g == Decimal("26.25")


def test_built_food_logs_as_one_line(client):
    add(client, item_id="3", amount="1", mode="servings")   # 1 of 2 servings of Lunch
    entry = LogEntry.query.one()
    assert entry.description == "Lunch" and entry.quantity == 1 and entry.unit == "serving"
    assert entry.calories_kcal == Decimal("240.5") and entry.meal_name is None


def test_edit_quantity_rescales_the_snapshot(client):
    add(client, item_id="1", amount="100", mode="amount")
    db.session.get(Food, 1).protein_g = 99  # the food changes...
    db.session.commit()
    client.post("/log/entry/1/edit", data={"quantity": "200"})
    entry = db.session.get(LogEntry, 1)
    assert entry.quantity == 200 and entry.protein_g == 50  # ...but the entry scales its own snapshot


def test_delete_entry(client):
    add(client, item_id="1", amount="1", mode="servings")
    resp = client.post("/log/entry/1/delete")
    assert resp.headers["Location"] == f"/log/{DAY}"
    assert LogEntry.query.count() == 0


def test_zero_amount_is_rejected(client):
    resp = add(client, item_id="1", amount="0", mode="servings")
    assert b"Enter an amount above zero" in resp.data
    assert LogEntry.query.count() == 0


def test_day_page_shows_entries_and_totals(client):
    add(client, item_id="1", amount="1", mode="servings")
    resp = client.get(f"/log/{DAY}")
    assert b"Tuna" in resp.data and b'<span class="tile-value">116</span>' in resp.data  # 115.5 kcal
    assert b"1 item" in resp.data


def test_catalogue_lists_every_food_with_favourites_first_and_tag_chips(client):
    html = client.get(f"/log/{DAY}").data.decode()
    cards = re.findall(r'<li data-name="([^"]+)" data-tags="([^"]*)" data-fav="(\d)"', html)
    assert cards == [("tuna", "|", "1"), ("avocado", "|", "0"), ("lunch", "|meal|", "0")]
    assert "116&nbsp;kcal" in html                        # tuna per serving (115.5)
    assert "1 of 2 servings · 2 ingredients" in html      # the built food's card
    assert 'data-filter="tag:meal"' in html               # a filter chip for each tag in use


def hx_add(client, **data):
    return client.post(f"/log/{DAY}/add", data=data, headers={"HX-Request": "true"})


def test_background_add_replies_with_page_updates_not_a_redirect(client):
    resp = hx_add(client, item_id="1", amount="1", mode="servings")
    html = resp.data.decode()
    assert resp.status_code == 200 and "<html" not in html
    assert 'id="day-total" hx-swap-oob="true"' in html and 'id="eaten" hx-swap-oob="true"' in html
    assert "Added Tuna (105 g). Day total 116 kcal." in html
    assert LogEntry.query.count() == 1


def test_undo_removes_what_the_last_add_created(client):
    hx_add(client, item_id="1", amount="1", mode="servings")                     # stays
    html = hx_add(client, item_id="3", amount="1", mode="servings").data.decode()  # undone
    ids = re.findall(r'name="entry_id" value="(\d+)"', html)
    assert len(ids) == 1
    html = client.post(f"/log/{DAY}/undo", data={"entry_id": ids}, headers={"HX-Request": "true"}).data.decode()
    assert "Removed 1 item." in html and [e.description for e in LogEntry.query] == ["Tuna"]


def test_background_add_with_zero_shows_an_error_message(client):
    html = hx_add(client, item_id="1", amount="0", mode="servings").data.decode()
    assert "toast-error" in html and "Enter an amount above zero" in html



def test_day_label_adds_the_year_only_for_other_years():
    today = date(2026, 10, 21)
    assert dates.day_label(date(2026, 10, 20), today) == "Yesterday"
    assert dates.day_label(date(2026, 3, 4), today) == "Wednesday 4 March"
    assert dates.day_label(date(2000, 1, 1), today) == "Saturday 1 January 2000"


def test_eaten_table_shows_each_items_macros_and_a_total_on_log_and_dashboard(client):
    add(client, item_id="1", amount="1", mode="servings")   # tuna: protein 26.25, salt 1.05
    add(client, item_id="2", amount="1", mode="servings")   # avocado: protein 1, fibre 5
    for url in (f"/log/{DAY}", f"/?day={DAY}"):
        html = client.get(url).data.decode()
        assert '<td class="num">26.3</td>' in html and '<td class="num">1.05</td>' in html   # tuna row
        assert '<td class="num">5</td>' in html                                               # avocado fibre
        foot = html[html.index("<tfoot>"):html.index("</tfoot>")]
        assert ">Total<" in foot and '<td class="num">27.3</td>' in foot                      # 26.25 + 1
        assert 'href="/log/entry/1/edit"' in html                                             # name opens the edit page


def test_catalogue_card_has_kcal_on_the_serving_line_and_a_labelled_plus_button(client):
    html = client.get(f"/log/{DAY}").data.decode()
    assert '<p class="product-serving"><span>105 g</span><span class="kcal-chip">116&nbsp;kcal</span></p>' in html
    assert 'class="product-add" aria-label="Add Tuna" title="Add">+</button>' in html
