from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import FoodForm
from ..models import Food
from ..services import nutrition

bp = Blueprint("foods", __name__, url_prefix="/foods")

FIELDS = ["name", "brand", "unit", "basis_amount", "protein_g", "carbs_g", "fat_g",
          "salt_g", "fibre_g", "serving_size", "serving_label"]


def _make_form(food=None):
    form = FoodForm(obj=food)
    form.unit.choices = [(u, u) for u in current_app.config["UNITS"]]
    return form


def _copy_form_to_food(form, food):
    for field in FIELDS:
        value = getattr(form, field).data
        if field.endswith("_g") and value is None:
            value = 0  # blank macro box means zero
        if field in ("brand", "serving_label") and not value:
            value = None
        setattr(food, field, value)


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    query = Food.query.order_by(Food.name)
    if q:
        query = query.filter(Food.name.ilike(f"%{q}%") | Food.brand.ilike(f"%{q}%"))
    foods = query.all()
    # HTMX sends this header; it only wants the list fragment, not the whole page.
    if request.headers.get("HX-Request"):
        return render_template("partials/_food_rows.html", foods=foods, q=q)
    return render_template("foods/list.html", foods=foods, q=q)


@bp.route("/new", methods=["GET", "POST"])
def new():
    form = _make_form()
    if form.validate_on_submit():
        food = Food()
        _copy_form_to_food(form, food)
        db.session.add(food)
        db.session.commit()
        flash(f"Added {food.name}.", "success")
        return redirect(url_for("foods.detail", food_id=food.id))
    return render_template("foods/form.html", form=form, food=None)


@bp.route("/<int:food_id>")
def detail(food_id):
    food = db.get_or_404(Food, food_id)
    return render_template(
        "foods/detail.html", food=food,
        per_basis=nutrition.macros_for(food, food.basis_amount),
        per_serving=nutrition.macros_per_serving(food),
    )


@bp.route("/<int:food_id>/edit", methods=["GET", "POST"])
def edit(food_id):
    food = db.get_or_404(Food, food_id)
    form = _make_form(food)
    if form.validate_on_submit():
        _copy_form_to_food(form, food)
        db.session.commit()
        flash(f"Saved {food.name}.", "success")
        return redirect(url_for("foods.detail", food_id=food.id))
    return render_template("foods/form.html", form=form, food=food)


@bp.route("/<int:food_id>/delete", methods=["POST"])
def delete(food_id):
    food = db.get_or_404(Food, food_id)
    try:
        db.session.delete(food)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f"{food.name} is used in a meal, so it can't be deleted yet.", "error")
        return redirect(url_for("foods.detail", food_id=food_id))
    flash(f"Deleted {food.name}.", "success")
    return redirect(url_for("foods.index"))


def _dec(value):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return Decimal(0)


@bp.route("/preview", methods=["POST"])
def preview():
    """HTMX fragment: macros per typical serving, recalculated as the form changes."""
    stand_in = SimpleNamespace(
        **{f: _dec(request.form.get(f)) for f in nutrition.MACROS},
        basis_amount=_dec(request.form.get("basis_amount")),
        serving_size=_dec(request.form.get("serving_size")),
    )
    if stand_in.basis_amount <= 0 or stand_in.serving_size <= 0:
        return render_template("partials/_macro_preview.html", macros=None)
    return render_template(
        "partials/_macro_preview.html",
        macros=nutrition.macros_per_serving(stand_in),
        calories=nutrition.calories(nutrition.macros_per_serving(stand_in)),
        unit=request.form.get("unit", ""),
        serving_size=stand_in.serving_size,
    )
