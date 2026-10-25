import uuid
from collections import Counter
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..forms import BuiltFoodForm, FoodForm
from ..models import Food, FoodIngredient, Tag
from ..services import nutrition, recipes
from ..services.label_parser import parse_label

bp = Blueprint("foods", __name__, url_prefix="/foods")

FIELDS = ["name", "unit", "basis_amount", "calories_kcal", "protein_g", "carbs_g", "fat_g",
          "fibre_g", "salt_g", "serving_size", "serving_label"]


def _dec(value, default=Decimal(0)):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return default


def _all_tags():
    return Tag.query.order_by(Tag.name).all()


def _set_tags(food):
    """Apply the tag chips ticked on the form, plus any new tag names typed in."""
    food.tags = recipes.find_or_create_tags(
        [int(t) for t in request.form.getlist("tag_ids") if t.isdigit()], request.form.get("new_tags"))


# --- List ------------------------------------------------------------------------------

@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    rows = _search(q, tag)
    # HTMX sends this header; it only wants the list fragment, not the whole page.
    if request.headers.get("HX-Request"):
        return render_template("partials/_food_rows.html", rows=rows, q=q, tag=tag)
    return render_template("foods/list.html", rows=rows, q=q, tag=tag, tags=_all_tags())


def _search(q, tag=""):
    """(food, macros per typical serving) pairs: favourites first, then alphabetical."""
    query = Food.query.options(selectinload(Food.tags)).order_by(Food.is_favourite.desc(), Food.name)
    if q:
        query = query.filter(Food.name.ilike(f"%{q}%"))
    if tag:
        query = query.filter(Food.tags.any(Tag.name == tag))
    return [(food, nutrition.macros_per_serving(food)) for food in query.all()]


@bp.route("/<int:food_id>/favourite", methods=["POST"])
def favourite(food_id):
    food = db.get_or_404(Food, food_id)
    food.is_favourite = not food.is_favourite
    db.session.commit()
    q, tag = request.form.get("q", "").strip(), request.form.get("tag", "").strip()
    return render_template("partials/_food_rows.html", rows=_search(q, tag), q=q, tag=tag)


# --- Plain foods (label values) ----------------------------------------------------------

def _make_form(food=None):
    form = FoodForm(obj=food)
    if food is not None and request.method == "GET":
        for field in nutrition.NUTRIENTS + ("basis_amount", "serving_size"):
            getattr(form, field).data = nutrition.tidy(getattr(form, field).data)
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
        _set_tags(food)
        db.session.add(food)
        db.session.commit()
        flash(f"Added {food.name}.", "success")
        return redirect(url_for("foods.detail", food_id=food.id))
    return render_template("foods/form.html", form=form, food=None, tags=_all_tags(), chosen=_posted_tag_ids())


def _posted_tag_ids():
    return {int(t) for t in request.form.getlist("tag_ids") if t.isdigit()}


@bp.route("/<int:food_id>")
def detail(food_id):
    food = db.get_or_404(Food, food_id)
    if food.is_built:
        return _built_page(food)
    return render_template(
        "foods/detail.html", food=food, used_in=recipes.used_in(food),
        per_basis=nutrition.macros_for(food, food.basis_amount),
        per_serving=nutrition.macros_per_serving(food),
    )


@bp.route("/<int:food_id>/edit", methods=["GET", "POST"])
def edit(food_id):
    food = db.get_or_404(Food, food_id)
    if food.is_built:
        return _built_edit(food)
    form = _make_form(food)
    if form.validate_on_submit():
        _copy_form_to_food(form, food)
        _set_tags(food)
        updated = recipes.refresh_dependents(food)
        db.session.commit()
        flash(f"Saved {food.name}." + (f" Updated {updated} built food{'' if updated == 1 else 's'} that use it."
                                       if updated else ""), "success")
        return redirect(url_for("foods.detail", food_id=food.id))
    chosen = _posted_tag_ids() if request.method == "POST" else {t.id for t in food.tags}
    return render_template("foods/form.html", form=form, food=food, tags=_all_tags(), chosen=chosen)


@bp.route("/<int:food_id>/delete", methods=["POST"])
def delete(food_id):
    food = db.get_or_404(Food, food_id)
    parents = recipes.used_in(food)
    try:
        if not parents:
            db.session.delete(food)
            db.session.commit()
    except IntegrityError:
        db.session.rollback()
        parents = parents or [None]
    if parents:
        # The check above is the friendly path; the database foreign key is the safety net.
        names = ", ".join(p.name for p in parents if p)
        flash(f"{food.name} is an ingredient in {names or 'another food'}, so it can't be deleted yet.", "error")
        return redirect(url_for("foods.detail", food_id=food_id))
    flash(f"Deleted {food.name}.", "success")
    return redirect(url_for("foods.index"))


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


# --- Built foods (made from other foods) --------------------------------------------------

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


def _resolve(rows, exclude_id=None):
    """Attach the matching food, quantity (in the food's unit) and macros to each row.

    Rows whose food text matches nothing, or whose amount isn't above zero, get item=None.
    """
    foods = Food.query.all()
    labels = food_labels(foods)
    by_label = {labels[f.id].casefold(): f for f in foods if f.id != exclude_id}
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


def _built_page(food):
    total, per_serving = _summary([SimpleNamespace(food=i.ingredient, quantity=i.quantity) for i in food.ingredients],
                                  food.recipe_servings)
    lines = [(i, nutrition.macros_for(i.ingredient, i.quantity)) for i in food.ingredients]
    return render_template("foods/built_detail.html", food=food, lines=lines, total=total, per_serving=per_serving,
                           servings=food.recipe_servings, has_items=bool(lines), used_in=recipes.used_in(food))


def _save_built(food, form):
    """Shared by build and edit. Returns a redirect on success, or None if the form needs showing again."""
    rows = _resolve(_rows_from_form(), exclude_id=food.id)
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
    try:
        recipes.check_no_loop(food, [i.food for i in items])
    except recipes.LoopError as loop:
        flash(f"{loop} already contains {food.name}, so it can't also be one of its ingredients.", "error")
        return None
    food.name = form.name.data
    food.recipe_servings = form.recipe_servings.data
    food.notes = form.notes.data or None
    food.ingredients = [FoodIngredient(ingredient=i.food, quantity=i.quantity) for i in items]
    _set_tags(food)
    db.session.add(food)
    db.session.flush()
    recipes.apply_totals(food)
    updated = recipes.refresh_dependents(food)
    db.session.commit()
    flash(f"Saved {food.name}." + (f" Updated {updated} built food{'' if updated == 1 else 's'} that use it."
                                   if updated else ""), "success")
    return redirect(url_for("foods.detail", food_id=food.id))


def _built_form_page(form, food, rows, chosen):
    rows = _resolve(rows or [_blank_row()], exclude_id=food.id if food else None)
    servings = form.recipe_servings.data or 1
    total, per_serving = _summary(_items(rows), servings)
    foods = [f for f in Food.query.order_by(Food.is_favourite.desc(), Food.name).all() if not food or f.id != food.id]
    return render_template("foods/built_form.html", form=form, food=food, rows=rows, foods=foods,
                           labels=food_labels(Food.query.all()), total=total, per_serving=per_serving,
                           servings=servings, has_items=bool(_items(rows)), tags=_all_tags(), chosen=chosen)


@bp.route("/build", methods=["GET", "POST"])
def build():
    food = Food()
    form = BuiltFoodForm()
    if request.method == "POST":
        response = _save_built(food, form)
        if response:
            return response
        db.session.rollback()
        return _built_form_page(form, None, _rows_from_form(), _posted_tag_ids())
    # New built foods start tagged Meal; it's an ordinary tag, so it can be unticked.
    meal = Tag.query.filter(Tag.name == recipes.MEAL_TAG).first()
    return _built_form_page(form, None, [], {meal.id} if meal else set())


def _built_edit(food):
    if request.method == "POST":
        form = BuiltFoodForm()
        response = _save_built(food, form)
        if response:
            return response
        db.session.rollback()
        return _built_form_page(form, food, _rows_from_form(), _posted_tag_ids())
    form = BuiltFoodForm(obj=food)
    form.recipe_servings.data = nutrition.tidy(form.recipe_servings.data)
    labels = food_labels(Food.query.all())
    rows = [{"key": _new_key(), "food": labels[i.ingredient_id], "amount": str(nutrition.tidy(i.quantity)),
             "mode": "amount"} for i in food.ingredients]
    return _built_form_page(form, food, rows, {t.id for t in food.tags})


@bp.route("/ingredient-row")
def ingredient_row():
    """HTMX fragment: one blank ingredient row to append to the builder."""
    return render_template("partials/_ingredient_row.html", row=_blank_row())


@bp.route("/build-preview", methods=["POST"])
def build_preview():
    """HTMX fragment: the totals, plus each row's own macros swapped in "out of band" by id."""
    exclude = request.form.get("food_id", type=int)
    rows = _resolve(_rows_from_form(), exclude_id=exclude)
    servings = _dec(request.form.get("recipe_servings"), Decimal(1))
    total, per_serving = _summary(_items(rows), servings)
    return render_template("partials/_recipe_preview.html", rows=rows, total=total, per_serving=per_serving,
                           servings=servings, has_items=bool(_items(rows)))
