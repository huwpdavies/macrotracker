from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import FoodForm
from ..models import Food, MealItem
from ..services import nutrition
from ..services.label_parser import parse_label

bp = Blueprint("foods", __name__, url_prefix="/foods")

FIELDS = ["name", "unit", "basis_amount", "calories_kcal", "protein_g", "carbs_g", "fat_g",
          "fibre_g", "salt_g", "serving_size", "serving_label"]


def _make_form(food=None):
    form = FoodForm(obj=food)
    form.unit.choices = [(u, u) for u in current_app.config["UNITS"]]
    return form


def _copy_form_to_food(form, food):
    for field in FIELDS:
        value = getattr(form, field).data
        if (field.endswith("_g") or field == "calories_kcal") and value is None:
            value = 0  # blank nutrient box means zero
        if field == "serving_label" and not value:
            value = None
        setattr(food, field, value)


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    foods = _search(q)
    # HTMX sends this header; it only wants the list fragment, not the whole page.
    if request.headers.get("HX-Request"):
        return render_template("partials/_food_rows.html", foods=foods, q=q)
    return render_template("foods/list.html", foods=foods, q=q)


def _search(q):
    """Favourites first, then alphabetical."""
    query = Food.query.order_by(Food.is_favourite.desc(), Food.name)
    if q:
        query = query.filter(Food.name.ilike(f"%{q}%"))
    return query.all()


@bp.route("/<int:food_id>/favourite", methods=["POST"])
def favourite(food_id):
    food = db.get_or_404(Food, food_id)
    food.is_favourite = not food.is_favourite
    db.session.commit()
    q = request.form.get("q", "").strip()
    return render_template("partials/_food_rows.html", foods=_search(q), q=q)


@bp.route("/parse-label", methods=["POST"])
def parse_label_text():
    """Fill the form from pasted label text. The browser sets the fields from this JSON."""
    text = (request.get_json(silent=True) or {}).get("text", "")
    return jsonify(parse_label(text))


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
    in_use = MealItem.query.filter_by(food_id=food_id).first() is not None
    try:
        if not in_use:
            db.session.delete(food)
            db.session.commit()
    except IntegrityError:
        db.session.rollback()
        in_use = True
    if in_use:
        # The check above is the friendly path; the database foreign key is the safety net.
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
        **{f: _dec(request.form.get(f)) for f in nutrition.NUTRIENTS},
        basis_amount=_dec(request.form.get("basis_amount")),
        serving_size=_dec(request.form.get("serving_size")),
    )
    if stand_in.basis_amount <= 0 or stand_in.serving_size <= 0:
        return render_template("partials/_macro_preview.html", macros=None)
    return render_template(
        "partials/_macro_preview.html",
        macros=nutrition.macros_per_serving(stand_in),
        unit=request.form.get("unit", ""),
        serving_size=stand_in.serving_size,
    )
