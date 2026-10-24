import uuid
from collections import Counter
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..forms import MealForm
from ..models import Food, Meal, MealItem
from ..services import nutrition

bp = Blueprint("meals", __name__, url_prefix="/meals")


def _dec(value, default=Decimal(0)):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return default


def _all_foods():
    return Food.query.order_by(Food.is_favourite.desc(), Food.name).all()


def food_labels(foods):
    """The text shown (and typed) for each food in the ingredient search box.

    Usually just the name; two foods with the same name get their unit and number added so they stay distinct.
    """
    counts = Counter(f.name for f in foods)
    return {f.id: f.name if counts[f.name] == 1 else f"{f.name} ({f.unit}, #{f.id})" for f in foods}


def _new_key():
    # Each row on the page gets a short id so the live preview can update that row's macros in place.
    return uuid.uuid4().hex[:8]


def _blank_row():
    return {"key": _new_key(), "food": "", "amount": "1", "mode": "servings"}


def _rows_from_form():
    """The raw ingredient rows as posted, so a form with errors can be shown again as typed."""
    return [
        {"key": k, "food": f.strip(), "amount": a, "mode": m}
        for k, f, a, m in zip(
            request.form.getlist("item_key"),
            request.form.getlist("item_food"),
            request.form.getlist("item_amount"),
            request.form.getlist("item_mode"),
        )
    ]


def _resolve(rows):
    """Attach the matching food, quantity (in the food's unit) and macros to each row.

    Rows whose food text matches nothing, or whose amount isn't above zero, get item=None.
    """
    foods = Food.query.all()
    labels = food_labels(foods)
    by_label = {labels[food.id].casefold(): food for food in foods}
    for row in rows:
        food = by_label.get(row["food"].casefold())
        amount = _dec(row["amount"])
        row["unknown"] = bool(row["food"]) and food is None
        row["item"] = None
        if food is None or amount <= 0:
            continue
        quantity = nutrition.quantity_from_servings(food, amount) if row["mode"] == "servings" else amount
        row["item"] = SimpleNamespace(food=food, quantity=quantity, macros=nutrition.macros_for(food, quantity))
    return rows


def _items(rows):
    return [row["item"] for row in rows if row["item"]]


def _summary(items, servings):
    total = nutrition.total_for_items(items)
    return total, nutrition.divide_macros(total, servings if servings > 0 else 1)


@bp.route("/")
def index():
    meals = Meal.query.order_by(Meal.is_favourite.desc(), Meal.name).all()
    if request.headers.get("HX-Request"):
        return render_template("partials/_meal_rows.html", meals=meals, per_serving=_per_serving(meals))
    return render_template("meals/list.html", meals=meals, per_serving=_per_serving(meals))


def _per_serving(meals):
    return {m.id: _summary(m.items, m.servings)[1] for m in meals}


@bp.route("/<int:meal_id>/favourite", methods=["POST"])
def favourite(meal_id):
    meal = db.get_or_404(Meal, meal_id)
    meal.is_favourite = not meal.is_favourite
    db.session.commit()
    return index()


@bp.route("/<int:meal_id>")
def detail(meal_id):
    meal = db.get_or_404(Meal, meal_id)
    total, per_serving = _summary(meal.items, meal.servings)
    lines = [(item, nutrition.macros_for(item.food, item.quantity)) for item in meal.items]
    return render_template("meals/detail.html", meal=meal, lines=lines, total=total, per_serving=per_serving,
                           servings=meal.servings, has_items=bool(meal.items))


def _save(meal, form):
    """Shared by new and edit. Returns a redirect on success, or None if the form needs showing again."""
    rows = _resolve(_rows_from_form())
    items = _items(rows)
    if not form.validate_on_submit():
        return None
    unknown = [row["food"] for row in rows if row["unknown"]]
    if unknown:
        flash(f"Couldn't find {', '.join(repr(u) for u in unknown)}. Pick foods from the suggestions.", "error")
        return None
    if not items:
        flash("Add at least one ingredient with an amount.", "error")
        return None
    meal.name = form.name.data
    meal.servings = form.servings.data
    meal.notes = form.notes.data or None
    meal.items = [MealItem(food=i.food, quantity=i.quantity) for i in items]
    db.session.add(meal)
    db.session.commit()
    flash(f"Saved {meal.name}.", "success")
    return redirect(url_for("meals.detail", meal_id=meal.id))


def _form_page(form, meal, rows):
    rows = _resolve(rows or [_blank_row()])
    servings = form.servings.data or 1
    total, per_serving = _summary(_items(rows), servings)
    foods = _all_foods()
    return render_template("meals/form.html", form=form, meal=meal, rows=rows, foods=foods, labels=food_labels(foods),
                           total=total, per_serving=per_serving, servings=servings, has_items=bool(_items(rows)))


@bp.route("/new", methods=["GET", "POST"])
def new():
    meal = Meal()
    form = MealForm()
    if request.method == "POST":
        response = _save(meal, form)
        if response:
            return response
        return _form_page(form, None, _rows_from_form())
    return _form_page(form, None, [])


@bp.route("/<int:meal_id>/edit", methods=["GET", "POST"])
def edit(meal_id):
    meal = db.get_or_404(Meal, meal_id)
    if request.method == "POST":
        form = MealForm()
        response = _save(meal, form)
        if response:
            return response
        db.session.rollback()
        return _form_page(form, meal, _rows_from_form())
    form = MealForm(obj=meal)
    form.servings.data = nutrition.tidy(form.servings.data)
    labels = food_labels(Food.query.all())
    rows = [{"key": _new_key(), "food": labels[i.food_id], "amount": str(nutrition.tidy(i.quantity)), "mode": "amount"}
            for i in meal.items]
    return _form_page(form, meal, rows)


@bp.route("/<int:meal_id>/delete", methods=["POST"])
def delete(meal_id):
    meal = db.get_or_404(Meal, meal_id)
    db.session.delete(meal)
    db.session.commit()
    flash(f"Deleted {meal.name}.", "success")
    return redirect(url_for("meals.index"))


@bp.route("/row")
def row():
    """HTMX fragment: one blank ingredient row to append to the form."""
    return render_template("partials/_meal_item_row.html", row=_blank_row())


@bp.route("/preview", methods=["POST"])
def preview():
    """HTMX fragment: the totals, plus each row's own macros swapped in "out of band" by id."""
    rows = _resolve(_rows_from_form())
    servings = _dec(request.form.get("servings"), Decimal(1))
    total, per_serving = _summary(_items(rows), servings)
    return render_template("partials/_meal_preview.html", rows=rows, total=total, per_serving=per_serving,
                           servings=servings, has_items=bool(_items(rows)))
