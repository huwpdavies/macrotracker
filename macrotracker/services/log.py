"""Logging food. Each entry stores a snapshot of its nutrition, so later edits
to a food or meal never change what was already logged."""
from decimal import Decimal

from ..extensions import db
from ..models import LogEntry
from . import nutrition


def _entry(day, food, quantity, meal_name=None):
    macros = nutrition.macros_for(food, quantity)
    return LogEntry(log_date=day, food_id=food.id, meal_name=meal_name,
                    description=food.name, quantity=quantity, unit=food.unit, **macros)


def log_food(day, food, quantity):
    """Log `quantity` (in the food's unit) of a food."""
    entry = _entry(day, food, Decimal(quantity))
    db.session.add(entry)
    db.session.commit()
    return entry


def log_meal(day, meal, servings_eaten):
    """Expand a meal into one entry per food, scaled to the servings eaten."""
    share = Decimal(servings_eaten) / Decimal(meal.servings)
    entries = [_entry(day, item.food, item.quantity * share, meal_name=meal.name) for item in meal.items]
    db.session.add_all(entries)
    db.session.commit()
    return entries


def change_quantity(entry, new_quantity):
    """Rescale the entry's own snapshot; the food is not read again."""
    new_quantity = Decimal(new_quantity)
    factor = new_quantity / Decimal(entry.quantity)
    for n in nutrition.NUTRIENTS:
        setattr(entry, n, Decimal(getattr(entry, n)) * factor)
    entry.quantity = new_quantity
    db.session.commit()


def entries_for(day):
    return LogEntry.query.filter_by(log_date=day).order_by(LogEntry.created_at, LogEntry.id).all()


def totals(entries):
    return nutrition.add_macros({n: Decimal(getattr(e, n)) for n in nutrition.NUTRIENTS} for e in entries)
