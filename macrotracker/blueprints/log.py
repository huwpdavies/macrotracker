from datetime import timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..forms import EntryForm
from ..models import Food, LogEntry, Meal
from ..services import dates, nutrition
from ..services import log as log_service

bp = Blueprint("log", __name__, url_prefix="/log")


def _day_or_404(day_text):
    """The day comes from the URL path, e.g. /log/2026-10-21."""
    day = dates.parse_day(day_text)
    if day is None:
        abort(404)
    return day


def _positive(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        return None
    return number if number > 0 else None


@bp.route("/")
def today():
    return redirect(url_for("log.day", day_text=dates.today_london().isoformat()))


@bp.route("/<day_text>")
def day(day_text):
    day = _day_or_404(day_text)
    entries = log_service.entries_for(day)
    return render_template(
        "log/day.html", day=day, entries=entries, totals=log_service.totals(entries),
        label=dates.day_label(day), long_date=dates.long_date(day),
        prev_day=(day - timedelta(days=1)).isoformat(), next_day=(day + timedelta(days=1)).isoformat(),
        is_today=day == dates.today_london(),
    )


@bp.route("/<day_text>/search")
def search(day_text):
    """HTMX fragment. The search words arrive in the query string: /log/2026-10-21/search?q=tuna"""
    day = _day_or_404(day_text)
    q = request.args.get("q", "").strip()
    foods = Food.query.order_by(Food.is_favourite.desc(), Food.name)
    meals = Meal.query.order_by(Meal.is_favourite.desc(), Meal.name)
    if q:
        foods = foods.filter(Food.name.ilike(f"%{q}%"))
        meals = meals.filter(Meal.name.ilike(f"%{q}%"))
    else:
        # Nothing typed yet: offer favourites as one-tap shortcuts.
        foods = foods.filter(Food.is_favourite.is_(True))
        meals = meals.filter(Meal.is_favourite.is_(True))
    return render_template("partials/_log_results.html", day=day, q=q,
                           foods=foods.limit(8).all(), meals=meals.limit(8).all())


@bp.route("/<day_text>/add", methods=["POST"])
def add(day_text):
    day = _day_or_404(day_text)
    back = redirect(url_for("log.day", day_text=day.isoformat()))
    amount = _positive(request.form.get("amount"))
    if amount is None:
        flash("Enter an amount above zero.", "error")
        return back

    if request.form.get("kind") == "meal":
        meal = db.get_or_404(Meal, request.form.get("item_id", type=int))
        if not meal.items:
            flash(f"{meal.name} has no ingredients yet.", "error")
            return back
        log_service.log_meal(day, meal, amount)
        flash(f"Logged {meal.name} ({len(meal.items)} items).", "success")
        return back

    food = db.get_or_404(Food, request.form.get("item_id", type=int))
    if request.form.get("mode") == "servings":
        amount = nutrition.quantity_from_servings(food, amount)
    log_service.log_food(day, food, amount)
    flash(f"Logged {food.name}.", "success")
    return back


@bp.route("/entry/<int:entry_id>/edit", methods=["GET", "POST"])
def edit_entry(entry_id):
    entry = db.get_or_404(LogEntry, entry_id)
    form = EntryForm(obj=entry)
    if request.method == "GET":
        form.quantity.data = nutrition.tidy(form.quantity.data)
    if form.validate_on_submit():
        log_service.change_quantity(entry, form.quantity.data)
        flash(f"Updated {entry.description}.", "success")
        return redirect(url_for("log.day", day_text=entry.log_date.isoformat()))
    return render_template("log/entry.html", entry=entry, form=form, label=dates.day_label(entry.log_date))


@bp.route("/entry/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id):
    entry = db.get_or_404(LogEntry, entry_id)
    day_text = entry.log_date.isoformat()
    db.session.delete(entry)
    db.session.commit()
    flash(f"Removed {entry.description}.", "success")
    return redirect(url_for("log.day", day_text=day_text))
