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
