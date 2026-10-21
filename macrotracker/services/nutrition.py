"""Nutrition maths as pure functions: no database, no Flask, easy to test.

A "food" here is anything with basis_amount, serving_size and the nutrient
attributes below (a Food row, or a plain stand-in used by the live preview).
"""
from decimal import Decimal

CALORIES = "calories_kcal"
MACROS = ("protein_g", "carbs_g", "fat_g", "salt_g", "fibre_g")
NUTRIENTS = (CALORIES,) + MACROS


def macros_for(food, quantity):
    """Calories and macros for `quantity` of the food's unit: value * quantity / basis_amount."""
    quantity = Decimal(quantity)
    basis = Decimal(food.basis_amount)
    return {n: Decimal(getattr(food, n)) * quantity / basis for n in NUTRIENTS}


def quantity_from_servings(food, servings):
    """Turn a number of servings into a quantity of the food's unit."""
    return Decimal(servings) * Decimal(food.serving_size)


def macros_per_serving(food):
    return macros_for(food, food.serving_size)


def add_macros(parts):
    """Sum several {nutrient: value} dicts."""
    total = {n: Decimal(0) for n in NUTRIENTS}
    for part in parts:
        for n in NUTRIENTS:
            total[n] += part[n]
    return total


def divide_macros(macros, divisor):
    divisor = Decimal(divisor)
    return {n: value / divisor for n, value in macros.items()}


def total_for_items(items):
    """Total nutrition for items that each have a `food` and a `quantity` (in the food's unit)."""
    return add_macros(macros_for(item.food, item.quantity) for item in items)


def tidy(value):
    """256.00 -> 256, 2.50 -> 2.5, so edit inputs show the same numbers as the detail pages."""
    if value is None:
        return value
    return value.quantize(Decimal(1)) if value == value.to_integral() else value.normalize()
