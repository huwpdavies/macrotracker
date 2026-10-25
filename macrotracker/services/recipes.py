"""Built foods: foods made from other foods, plus tags.

A built food stores its own per-serving numbers (worked out from its ingredients), so the rest
of the app treats it like any other food. When an ingredient changes, every built food that
uses it is worked out again; log entries are snapshots and never change.
"""
from decimal import ROUND_HALF_UP, Decimal

from ..extensions import db
from ..models import Food, FoodIngredient, Tag
from . import nutrition

DEFAULT_TAGS = ["Meal", "Fruit", "Snack", "Carb", "Meat", "Fibre", "Dessert"]
MEAL_TAG = "Meal"
CENT = Decimal("0.01")


class LoopError(ValueError):
    """An ingredient that already contains this food (directly or further down) would make a loop."""


def recipe_total(food):
    """Nutrition of the whole recipe."""
    return nutrition.add_macros(nutrition.macros_for(i.ingredient, i.quantity) for i in food.ingredients)


def apply_totals(food):
    """Set a built food's own numbers: one serving = whole recipe / servings it makes."""
    per_serving = nutrition.divide_macros(recipe_total(food), food.recipe_servings)
    for name, value in per_serving.items():
        setattr(food, name, value.quantize(CENT, rounding=ROUND_HALF_UP))  # the columns hold 2 decimal places
    food.unit, food.basis_amount, food.serving_size = "serving", 1, 1


def uses(food, target):
    """Does `food` contain `target`, directly or inside one of its own ingredients?"""
    return any(i.ingredient_id == target.id or uses(i.ingredient, target) for i in food.ingredients)


def check_no_loop(food, ingredient_foods):
    if food.id is None:  # a food that doesn't exist yet can't be inside anything
        return
    for ingredient in ingredient_foods:
        if ingredient.id == food.id or uses(ingredient, food):
            raise LoopError(ingredient.name)


def refresh_dependents(food):
    """After `food` changes, work out again every built food that uses it, however far up.

    Each built food is recomputed after any affected built food inside it, so nested recipes
    (wraps inside a lunch) always use up-to-date numbers.
    """
    affected, todo = set(), [food.id]
    while todo:
        parents = [row[0] for row in db.session.query(FoodIngredient.food_id)
                   .filter(FoodIngredient.ingredient_id == todo.pop()).distinct()]
        for parent_id in parents:
            if parent_id not in affected:
                affected.add(parent_id)
                todo.append(parent_id)

    done = set()

    def visit(built):
        if built.id in done:
            return
        for line in built.ingredients:
            if line.ingredient_id in affected:
                visit(line.ingredient)
        apply_totals(built)
        done.add(built.id)

    for food_id in affected:
        visit(db.session.get(Food, food_id))
    return len(affected)


def used_in(food):
    """Built foods that list `food` as an ingredient (directly)."""
    return (Food.query.join(FoodIngredient, FoodIngredient.food_id == Food.id)
            .filter(FoodIngredient.ingredient_id == food.id).order_by(Food.name).distinct().all())


def ensure_default_tags():
    existing = {t.name.casefold() for t in Tag.query.all()}
    for name in DEFAULT_TAGS:
        if name.casefold() not in existing:
            db.session.add(Tag(name=name))


def find_or_create_tags(tag_ids, new_names):
    """Tags ticked on a form, plus any typed as new (comma separated). Matching ignores case."""
    tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
    by_name = {t.name.casefold(): t for t in Tag.query.all()}
    for raw in (new_names or "").split(","):
        name = " ".join(raw.split())[:40]
        if not name:
            continue
        tag = by_name.get(name.casefold())
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            by_name[name.casefold()] = tag
        if tag not in tags:
            tags.append(tag)
    return tags
