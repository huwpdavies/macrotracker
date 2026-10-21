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


def _blank_row():
    return {"food_id": "", "amount": "1", "mode": "servings"}


def _rows_from_form():
    """The raw ingredient rows as posted, so a form with errors can be shown again as typed."""
    return [
        {"food_id": f, "amount": a, "mode": m}
        for f, a, m in zip(
            request.form.getlist("item_food_id"),
            request.form.getlist("item_amount"),
            request.form.getlist("item_mode"),
        )
    ]


def _items_from_rows(rows):
    """Turn posted rows into (food, quantity-in-the-food's-unit) items. Blank or bad rows are skipped."""
    foods = {str(f.id): f for f in Food.query.all()}
    items = []
    for row in rows:
        food = foods.get(row["food_id"])
        amount = _dec(row["amount"])
        if food is None or amount <= 0:
            continue
        if row["mode"] == "servings":
            amount = nutrition.quantity_from_servings(food, amount)
        items.append(SimpleNamespace(food=food, quantity=amount))
    return items


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
    rows = _rows_from_form()
    items = _items_from_rows(rows)
    if not form.validate_on_submit():
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
    items = _items_from_rows(rows)
    total, per_serving = _summary(items, form.servings.data or 1)
    return render_template("meals/form.html", form=form, meal=meal, rows=rows or [_blank_row()],
                           foods=_all_foods(), total=total, per_serving=per_serving)


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
    rows = [{"food_id": str(i.food_id), "amount": str(nutrition.tidy(i.quantity)), "mode": "amount"}
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
    return render_template("partials/_meal_item_row.html", row=_blank_row(), foods=_all_foods())


@bp.route("/preview", methods=["POST"])
def preview():
    """HTMX fragment: meal totals recalculated from the rows currently in the form."""
    items = _items_from_rows(_rows_from_form())
    servings = _dec(request.form.get("servings"), Decimal(1))
    total, per_serving = _summary(items, servings)
    return render_template("partials/_meal_totals.html", total=total, per_serving=per_serving,
                           servings=servings, has_items=bool(items))
