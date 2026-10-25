from datetime import datetime, timezone

from sqlalchemy import Index, text

from .extensions import db
from .services.dates import today_london


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


# Many-to-many: a food can have any number of tags, and a tag any number of foods.
food_tag = db.Table(
    "food_tag",
    db.Column("food_id", db.Integer, db.ForeignKey("food.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), nullable=False, unique=True)


class Food(db.Model):
    """Everything you eat is a food. A plain food has label values; a built food also has
    ingredients (other foods), and its values are worked out from them (services/recipes.py)."""
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
    # Built foods only: how many servings the whole recipe makes. None means a plain food.
    recipe_servings = db.Column(db.Numeric(8, 2))
    notes = db.Column(db.Text)
    is_favourite = _favourite_column()
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    ingredients = db.relationship(
        "FoodIngredient", foreign_keys="FoodIngredient.food_id", back_populates="food",
        cascade="all, delete-orphan", order_by="FoodIngredient.id",
    )
    tags = db.relationship("Tag", secondary=food_tag, order_by="Tag.name", backref="foods")

    @property
    def is_built(self):
        return self.recipe_servings is not None


class FoodIngredient(db.Model):
    """One line of a built food: `quantity` of `ingredient`, in the ingredient's own unit."""
    id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food.id", ondelete="CASCADE"), nullable=False, index=True)
    # No cascade here: a food that's used as an ingredient can't be deleted out from under a recipe.
    ingredient_id = db.Column(db.Integer, db.ForeignKey("food.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(8, 2), nullable=False)

    food = db.relationship("Food", foreign_keys=[food_id], back_populates="ingredients")
    ingredient = db.relationship("Food", foreign_keys=[ingredient_id])


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
    log_date = db.Column(db.Date, nullable=False, default=today_london, index=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food.id", ondelete="SET NULL"))
    # Only on entries from before meals became foods: the meal each line was part of.
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
