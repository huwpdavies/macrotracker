from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Tag, food_tag

bp = Blueprint("tags", __name__, url_prefix="/tags")


def _clean(name):
    return " ".join((name or "").split())[:40]


def _taken(name, other_than=None):
    query = Tag.query.filter(func.lower(Tag.name) == name.lower())
    if other_than is not None:
        query = query.filter(Tag.id != other_than)
    return query.first() is not None


@bp.route("/")
def index():
    counts = dict(db.session.query(food_tag.c.tag_id, func.count()).group_by(food_tag.c.tag_id).all())
    tags = Tag.query.order_by(Tag.name).all()
    return render_template("tags/index.html", tags=tags, counts=counts)


@bp.route("/", methods=["POST"])
def create():
    name = _clean(request.form.get("name"))
    if not name:
        flash("Type a name for the new tag.", "error")
    elif _taken(name):
        flash(f"There's already a tag called {name}.", "error")
    else:
        db.session.add(Tag(name=name))
        db.session.commit()
        flash(f"Added the {name} tag.", "success")
    return redirect(url_for("tags.index"))


@bp.route("/<int:tag_id>/rename", methods=["POST"])
def rename(tag_id):
    tag = db.get_or_404(Tag, tag_id)
    name = _clean(request.form.get("name"))
    if not name:
        flash("A tag needs a name.", "error")
    elif _taken(name, other_than=tag.id):
        flash(f"There's already a tag called {name}.", "error")
    else:
        old, tag.name = tag.name, name
        db.session.commit()
        flash(f"Renamed {old} to {name}.", "success")
    return redirect(url_for("tags.index"))


@bp.route("/<int:tag_id>/delete", methods=["POST"])
def delete(tag_id):
    tag = db.get_or_404(Tag, tag_id)
    db.session.delete(tag)  # removes it from its foods too (the link rows cascade)
    db.session.commit()
    flash(f"Deleted the {tag.name} tag. The foods themselves are unchanged.", "success")
    return redirect(url_for("tags.index"))
