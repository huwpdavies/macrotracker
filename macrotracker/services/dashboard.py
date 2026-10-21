"""Numbers for the dashboard: the day's totals (added up by the database) and
how each one compares with the active goal."""
from decimal import Decimal

from sqlalchemy import func

from ..extensions import db
from ..models import LogEntry
from .nutrition import NUTRIENTS

# key, label, unit, decimal places shown
ROWS = [
    ("calories_kcal", "Calories", "kcal", 0),
    ("protein_g", "Protein", "g", 1),
    ("carbs_g", "Carbs", "g", 1),
    ("fat_g", "Fat", "g", 1),
    ("fibre_g", "Fibre", "g", 1),
    ("salt_g", "Salt", "g", 2),
]
ON_TARGET = (Decimal(90), Decimal(110))   # percent of goal that counts as "on target"
MORE_IS_BETTER = {"protein_g", "fibre_g"}  # going over these is a win, not a warning
LIMITS = {"salt_g"}                        # a ceiling, not a target: anything over 100% is a warning


def day_totals(day):
    """One query: SELECT sum(...) for each nutrient. coalesce turns an empty day into zeros."""
    columns = [func.coalesce(func.sum(getattr(LogEntry, n)), 0) for n in NUTRIENTS]
    row = db.session.query(*columns).filter(LogEntry.log_date == day).one()
    return {n: Decimal(str(value)) for n, value in zip(NUTRIENTS, row)}


def progress(totals, goal):
    """One dict per nutrient with everything the template shows, so the template does no maths."""
    rows = []
    for key, label, unit, places in ROWS:
        eaten = totals[key]
        target = Decimal(getattr(goal, key)) if goal else Decimal(0)
        row = {"key": key, "label": label, "unit": unit, "places": places,
               "eaten": eaten, "target": target, "percent": None, "status": "no-target", "tone": "plain"}
        if target > 0:
            percent = eaten / target * 100
            row["percent"] = percent
            row["remaining"] = target - eaten
            if key in LIMITS and percent > 100:
                row["status"] = "over"
                row["tone"] = "warn"
            elif percent < ON_TARGET[0]:
                row["status"] = "under"
            elif percent <= ON_TARGET[1]:
                row["status"] = "on"
                row["tone"] = "good"
            else:
                row["status"] = "over"
                row["tone"] = "celebrate" if key in MORE_IS_BETTER else "warn"
        rows.append(row)
    return rows


def cheer(rows, has_entries):
    """One friendly line for the top of the dashboard. Problems first, then wins, then encouragement."""
    by_key = {r["key"]: r for r in rows}
    if not has_entries:
        return "A fresh page. What's first today?"
    warnings = [r["label"].lower() for r in rows if r["tone"] == "warn"]
    if warnings:
        return f"Heads up: you're over on {' and '.join(warnings)}."
    protein = by_key["protein_g"]
    if protein["status"] in ("on", "over"):
        return "Protein goal reached. Nice work!"
    if protein["percent"] is not None and protein["percent"] >= 50:
        return f"Nice! {int(protein['percent'])}% of your protein is done."
    return "Good start. Keep logging as you go."
