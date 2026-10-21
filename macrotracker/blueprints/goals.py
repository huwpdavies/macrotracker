from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..forms import GoalForm
from ..models import Goal
from ..services import goals as goal_service
from ..services import nutrition

bp = Blueprint("goals", __name__, url_prefix="/goals")


def _copy_form_to_goal(form, goal):
    goal.name = form.name.data
    for field in nutrition.NUTRIENTS:
        value = getattr(form, field).data
        setattr(goal, field, 0 if value is None else value)  # blank box means zero


def _make_form(goal=None):
    form = GoalForm(obj=goal)
    if goal is not None and request.method == "GET":
        for field in nutrition.NUTRIENTS:
            getattr(form, field).data = nutrition.tidy(getattr(form, field).data)
    return form


@bp.route("/")
def index():
    goals = Goal.query.order_by(Goal.is_active.desc(), Goal.name).all()
    return render_template("goals/list.html", goals=goals)


@bp.route("/new", methods=["GET", "POST"])
def new():
    form = _make_form()
    if form.validate_on_submit():
        goal = Goal()
        _copy_form_to_goal(form, goal)
        goal_service.add(goal)
        flash(f"Added {goal.name}." + (" It's your active goal." if goal.is_active else ""), "success")
        return redirect(url_for("goals.detail", goal_id=goal.id))
    return render_template("goals/form.html", form=form, goal=None)


@bp.route("/<int:goal_id>")
def detail(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    return render_template("goals/detail.html", goal=goal)


@bp.route("/<int:goal_id>/edit", methods=["GET", "POST"])
def edit(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    form = _make_form(goal)
    if form.validate_on_submit():
        _copy_form_to_goal(form, goal)
        db.session.commit()
        flash(f"Saved {goal.name}.", "success")
        return redirect(url_for("goals.detail", goal_id=goal.id))
    return render_template("goals/form.html", form=form, goal=goal)


@bp.route("/<int:goal_id>/activate", methods=["POST"])
def activate(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    goal_service.activate(goal)
    flash(f"{goal.name} is now your active goal.", "success")
    next_url = request.form.get("next", "")
    # Only follow paths on this site, never another domain.
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("goals.index")
    return redirect(next_url)


@bp.route("/<int:goal_id>/delete", methods=["POST"])
def delete(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    replacement_id = request.form.get("replacement_id", type=int)
    replacement = db.session.get(Goal, replacement_id) if replacement_id else None
    try:
        goal_service.delete(goal, replacement)
    except goal_service.ReplacementNeeded:
        # Ask which goal should take over before deleting the active one.
        others = Goal.query.filter(Goal.id != goal.id).order_by(Goal.name).all()
        return render_template("goals/replace.html", goal=goal, others=others)
    flash(f"Deleted {goal.name}." + (f" {replacement.name} is now active." if replacement else ""), "success")
    return redirect(url_for("goals.index"))
