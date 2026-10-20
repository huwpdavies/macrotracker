from datetime import date, datetime, timezone

from sqlalchemy import Index, text

from .extensions import db


def _now():
    return datetime.now(timezone.utc)


def _macro_column():
    return db.Column(db.Numeric(8, 2), nullable=False, default=0)


def _calories_column():
    # Typed in from the product label, not derived. server_default lets the
    # migration add this column to tables that already have rows.
    return db.Column(db.Numeric(8, 2), nullable=False, default=0, server_default=text("0"))


def _favourite_column():
    return db.Column(db.Boolean, nullable=False, default=False, server_default=text("false"))


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(30), nullable=False, default="g")
    # Macros below are "per basis_amount of unit", e.g. per 100 g or per 1 unit.
    basis_amount = db.Column(db.Numeric(8, 2), nullable=False, default=100)
    calories_kcal = _calories_column()
    protein_g = _macro_column()
    carbs_g = _macro_column()
    fat_g = _macro_column()
    salt_g = _macro_column()
    fibre_g = _macro_column()
    # A typical serving, as a quantity of the unit (105 g, or 0.5 unit).
    serving_size = db.Column(db.Numeric(8, 2), nullable=False, default=100)
    serving_label = db.Column(db.String(100))
    is_favourite = _favourite_column()
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)


class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)
    is_favourite = _favourite_column()
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    items = db.relationship(
        "MealItem", back_populates="meal", cascade="all, delete-orphan"
    )


class MealItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(db.Integer, db.ForeignKey("meal.id", ondelete="CASCADE"), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey("food.id"), nullable=False)
    # In the food's unit (not servings).
    quantity = db.Column(db.Numeric(8, 2), nullable=False)

    meal = db.relationship("Meal", back_populates="items")
    food = db.relationship("Food")


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    calories_kcal = _calories_column()
    protein_g = _macro_column()
    carbs_g = _macro_column()
    fat_g = _macro_column()
    salt_g = _macro_column()
    fibre_g = _macro_column()
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    # The database itself refuses a second active goal (a partial unique index).
    __table_args__ = (
        Index(
            "uq_goal_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
    )


class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food.id", ondelete="SET NULL"))
    meal_name = db.Column(db.String(200))
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(8, 2), nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    # Snapshot of this entry's nutrition, so later food edits don't rewrite history.
    calories_kcal = _calories_column()
    protein_g = _macro_column()
    carbs_g = _macro_column()
    fat_g = _macro_column()
    salt_g = _macro_column()
    fibre_g = _macro_column()
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    food = db.relationship("Food")
