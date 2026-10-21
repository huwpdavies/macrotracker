from datetime import timedelta

from flask import Blueprint, abort, render_template, request

from ..models import Goal
from ..services import dashboard, dates
from ..services import log as log_service

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    # The day is an option on the home page, so it comes from the query string: /?day=2026-10-20
    day_text = request.args.get("day")
    day = dates.parse_day(day_text) if day_text else dates.today_london()
    if day is None:
        abort(404)
    goal = Goal.query.filter_by(is_active=True).first()
    rows = dashboard.progress(dashboard.day_totals(day), goal)
    return render_template(
        "dashboard/index.html", day=day, goal=goal, entries=log_service.entries_for(day),
        calories=rows[0], nutrients=rows[1:],
        label=dates.day_label(day), long_date=dates.long_date(day),
        prev_day=(day - timedelta(days=1)).isoformat(), next_day=(day + timedelta(days=1)).isoformat(),
        is_today=day == dates.today_london(),
    )


@bp.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}
