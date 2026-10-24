from datetime import timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..forms import EntryForm
from ..models import Food, LogEntry, Meal, MealItem
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
        "log/day.html", day=day, entries=entries, totals=log_service.totals(entries), cards=_catalogue(),
        label=dates.day_label(day), long_date=dates.long_date(day),
        prev_day=(day - timedelta(days=1)).isoformat(), next_day=(day + timedelta(days=1)).isoformat(),
        is_today=day == dates.today_london(),
    )


def _catalogue():
    """Every meal and food as a card, favourites first, each with its per-serving nutrition."""
    meals = (Meal.query.options(selectinload(Meal.items).selectinload(MealItem.food))
             .order_by(Meal.is_favourite.desc(), Meal.name).all())
    foods = Food.query.order_by(Food.is_favourite.desc(), Food.name).all()
    cards = [{"kind": "meal", "item": m, "name": m.name,
              "serving": f"1 of {nutrition.tidy(m.servings)} serving{'' if m.servings == 1 else 's'} · {len(m.items)} foods",
              "macros": nutrition.divide_macros(nutrition.total_for_items(m.items), m.servings)}
             for m in meals if m.items]
    cards += [{"kind": "food", "item": f, "name": f.name,
               "serving": (f"{f.serving_label} · " if f.serving_label else "") + f"{nutrition.tidy(f.serving_size)} {f.unit}",
               "macros": nutrition.macros_per_serving(f)}
              for f in foods]
    # Favourites first across both kinds, then meals before foods, then by name.
    return sorted(cards, key=lambda c: (not c["item"].is_favourite, c["kind"] != "meal", c["name"].casefold()))


def _updates(day, message=None, undo_ids=(), error=False):
    """HTMX reply after adding or undoing in the background: the day total, the Eaten list and a
    short message are swapped into the page out of band, so nothing else reloads."""
    entries = log_service.entries_for(day)
    return render_template("partials/_log_updates.html", day=day, entries=entries, totals=log_service.totals(entries),
                           is_today=day == dates.today_london(), message=message, undo_ids=undo_ids, error=error)


@bp.route("/<day_text>/add", methods=["POST"])
def add(day_text):
    """Log a food or meal. From the catalogue (HTMX) it replies with page updates; otherwise it redirects."""
    day = _day_or_404(day_text)
    in_background = bool(request.headers.get("HX-Request"))

    def done(message, entries=(), error=False):
        if in_background:
            return _updates(day, message, [e.id for e in entries], error)
        flash(message, "error" if error else "success")
        return redirect(url_for("log.day", day_text=day.isoformat()))

    amount = _positive(request.form.get("amount"))
    if amount is None:
        return done("Enter an amount above zero.", error=True)

    if request.form.get("kind") == "meal":
        meal = db.get_or_404(Meal, request.form.get("item_id", type=int))
        if not meal.items:
            return done(f"{meal.name} has no ingredients yet.", error=True)
        entries = log_service.log_meal(day, meal, amount)
        return done(f"Added {meal.name} ({nutrition.tidy(amount)} serving{'' if amount == 1 else 's'}).", entries)

    food = db.get_or_404(Food, request.form.get("item_id", type=int))
    quantity = nutrition.quantity_from_servings(food, amount) if request.form.get("mode") == "servings" else amount
    entry = log_service.log_food(day, food, quantity)
    return done(f"Added {food.name} ({nutrition.tidy(quantity)} {food.unit}).", [entry])


@bp.route("/<day_text>/undo", methods=["POST"])
def undo(day_text):
    """Remove the entries the last background add created (the Undo button in the message)."""
    day = _day_or_404(day_text)
    ids = [int(i) for i in request.form.getlist("entry_id") if i.isdigit()]
    removed = LogEntry.query.filter(LogEntry.id.in_(ids), LogEntry.log_date == day).delete(synchronize_session=False)
    db.session.commit()
    return _updates(day, f"Undone. Removed {removed} item{'' if removed == 1 else 's'}.")


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
