from flask import Blueprint, render_template

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    return render_template("dashboard/index.html")


@bp.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}
