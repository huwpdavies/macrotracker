from flask import Blueprint, render_template

from ..models import Food, Goal, Meal

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    # Placeholder home page until the real dashboard (Phase 7).
    return render_template(
        "dashboard/index.html",
        food_count=Food.query.count(),
        meal_count=Meal.query.count(),
        active_goal=Goal.query.filter_by(is_active=True).first(),
    )


@bp.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}
