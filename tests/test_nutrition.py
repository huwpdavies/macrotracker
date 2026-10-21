from decimal import Decimal
from types import SimpleNamespace

from macrotracker.services import nutrition

TUNA = SimpleNamespace(basis_amount=100, serving_size=105, protein_g=25, carbs_g=0,
                       fat_g=1, salt_g=1, fibre_g=0, calories_kcal=110)
AVOCADO = SimpleNamespace(basis_amount=1, serving_size=Decimal("0.5"), protein_g=2, carbs_g=12,
                          fat_g=22, salt_g=0, fibre_g=10, calories_kcal=250)


def test_tuna_can_serving():
    m = nutrition.macros_per_serving(TUNA)
    assert m["protein_g"] == Decimal("26.25")
    assert m["salt_g"] == Decimal("1.05")


def test_avocado_half_serving_is_half_the_per_unit_macros():
    m = nutrition.macros_per_serving(AVOCADO)
    assert m["fat_g"] == 11
    assert m["fibre_g"] == 5


def test_quantity_from_servings():
    assert nutrition.quantity_from_servings(TUNA, 2) == 210
    assert nutrition.quantity_from_servings(AVOCADO, 1) == Decimal("0.5")


def test_calories_scale_with_serving():
    assert nutrition.macros_per_serving(TUNA)["calories_kcal"] == Decimal("115.5")
    assert nutrition.macros_per_serving(AVOCADO)["calories_kcal"] == 125


def test_total_for_items_and_per_serving():
    items = [SimpleNamespace(food=TUNA, quantity=105), SimpleNamespace(food=AVOCADO, quantity=Decimal("0.5"))]
    total = nutrition.total_for_items(items)
    assert total["calories_kcal"] == Decimal("240.5")
    assert total["protein_g"] == Decimal("27.25")
    assert nutrition.divide_macros(total, 2)["calories_kcal"] == Decimal("120.25")
