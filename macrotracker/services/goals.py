"""Rules for goals. The database guarantees at most one active goal (a partial
unique index); these functions keep the app friendly and always leave the data
in a valid state by doing each change in a single transaction."""
from ..extensions import db
from ..models import Goal


class ReplacementNeeded(Exception):
    """Deleting the active goal while other goals exist: the caller must pick the next active one."""


def add(goal):
    """Save a new goal. It becomes active if no goal is active yet."""
    if Goal.query.filter_by(is_active=True).first() is None:
        goal.is_active = True
    db.session.add(goal)
    db.session.commit()


def activate(goal):
    """Make `goal` the only active goal, in one transaction."""
    try:
        # Two statements on purpose: switch the old one off first, so the unique
        # index never sees two active goals at the same moment.
        Goal.query.filter(Goal.id != goal.id, Goal.is_active.is_(True)).update({"is_active": False})
        db.session.flush()
        goal.is_active = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def delete(goal, replacement=None):
    """Delete a goal. If it is active and others exist, `replacement` becomes active in the same transaction."""
    if goal.is_active and Goal.query.filter(Goal.id != goal.id).count() > 0:
        if replacement is None or replacement.id == goal.id:
            raise ReplacementNeeded()
        try:
            goal.is_active = False
            db.session.flush()
            replacement.is_active = True
            db.session.delete(goal)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        return
    db.session.delete(goal)
    db.session.commit()
