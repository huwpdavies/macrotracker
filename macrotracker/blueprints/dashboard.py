from flask import Blueprint, render_template

from ..models import Food, Goal

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    # Temporary Phase 2 check that the app can read the database.
    food_count = Food.query.count()
    active_goal = Goal.query.filter_by(is_active=True).first()
    return render_template(
        "dashboard/index.html", food_count=food_count, active_goal=active_goal
    )


@bp.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}
