"""Macro maths as pure functions: no database, no Flask, easy to test.

A "food" here is anything with basis_amount, serving_size and the five macro
attributes (a Food row, or a plain stand-in used by the live preview).
"""
from decimal import Decimal

MACROS = ("protein_g", "carbs_g", "fat_g", "salt_g", "fibre_g")


def macros_for(food, quantity):
    """Macros for `quantity` of the food's unit: food.macro * quantity / basis_amount."""
    quantity = Decimal(quantity)
    basis = Decimal(food.basis_amount)
    return {m: Decimal(getattr(food, m)) * quantity / basis for m in MACROS}


def quantity_from_servings(food, servings):
    """Turn a number of servings into a quantity of the food's unit."""
    return Decimal(servings) * Decimal(food.serving_size)


def calories(macros):
    """Derived, never stored: protein x4, carbs x4, fat x9."""
    return (
        Decimal(macros["protein_g"]) * 4
        + Decimal(macros["carbs_g"]) * 4
        + Decimal(macros["fat_g"]) * 9
    )


def macros_per_serving(food):
    return macros_for(food, food.serving_size)
