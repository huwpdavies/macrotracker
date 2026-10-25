"""Foods can be built from other foods; tags. Existing meals become built foods.

The old meal and meal_item tables are left in place (and unused by the app) so the
previously deployed version keeps working until the new one is live. A later migration
can drop them.

Revision ID: 5d2a8c1f9b3e
Revises: 9c3e5387eea2
Create Date: 2026-10-25

"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from alembic import op
import sqlalchemy as sa


revision = '5d2a8c1f9b3e'
down_revision = '9c3e5387eea2'
branch_labels = None
depends_on = None

DEFAULT_TAGS = ["Meal", "Fruit", "Snack", "Carb", "Meat", "Fibre", "Dessert"]
NUTRIENTS = ["calories_kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "salt_g"]


def upgrade():
    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'food_tag',
        sa.Column('food_id', sa.Integer(), sa.ForeignKey('food.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tag_id', sa.Integer(), sa.ForeignKey('tag.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('food_id', 'tag_id'),
    )
    op.create_table(
        'food_ingredient',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('food_id', sa.Integer(), sa.ForeignKey('food.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), sa.ForeignKey('food.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_food_ingredient_food_id', 'food_ingredient', ['food_id'])
    op.create_index('ix_food_ingredient_ingredient_id', 'food_ingredient', ['ingredient_id'])
    with op.batch_alter_table('food', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recipe_servings', sa.Numeric(precision=8, scale=2), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    # --- data: starting tags, then each meal becomes a built food tagged Meal ---
    conn = op.get_bind()
    tag = sa.table('tag', sa.column('id', sa.Integer), sa.column('name', sa.String))
    # Column types are given so decimals and dates are converted correctly on every database.
    num = sa.Numeric(8, 2)
    food = sa.table(
        'food', sa.column('id', sa.Integer), sa.column('name', sa.String), sa.column('unit', sa.String),
        sa.column('basis_amount', num), *[sa.column(n, num) for n in NUTRIENTS], sa.column('serving_size', num),
        sa.column('serving_label', sa.String), sa.column('recipe_servings', num), sa.column('notes', sa.Text),
        sa.column('is_favourite', sa.Boolean), sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)))
    food_tag = sa.table('food_tag', sa.column('food_id', sa.Integer), sa.column('tag_id', sa.Integer))
    food_ingredient = sa.table('food_ingredient', sa.column('food_id', sa.Integer), sa.column('ingredient_id', sa.Integer),
                               sa.column('quantity', num))
    meal = sa.table('meal', sa.column('id', sa.Integer), sa.column('name', sa.String), sa.column('notes', sa.Text),
                    sa.column('servings', num), sa.column('is_favourite', sa.Boolean),
                    sa.column('created_at', sa.DateTime(timezone=True)))
    meal_item = sa.table('meal_item', sa.column('id', sa.Integer), sa.column('meal_id', sa.Integer),
                         sa.column('food_id', sa.Integer), sa.column('quantity', num))

    for name in DEFAULT_TAGS:
        conn.execute(tag.insert().values(name=name))
    meal_tag_id = conn.execute(sa.select(tag.c.id).where(tag.c.name == "Meal")).scalar_one()

    cent = Decimal("0.01")
    now = datetime.now(timezone.utc)
    for m in conn.execute(sa.select(meal).order_by(meal.c.id)).mappings().all():
        lines = conn.execute(
            sa.select(meal_item.c.quantity, food).select_from(meal_item.join(food, meal_item.c.food_id == food.c.id))
            .where(meal_item.c.meal_id == m["id"]).order_by(meal_item.c.id)
        ).mappings().all()
        servings = Decimal(str(m["servings"] or 1))
        per_serving = {}
        for n in NUTRIENTS:
            total = sum((Decimal(str(l[n])) * Decimal(str(l["quantity"])) / Decimal(str(l["basis_amount"])) for l in lines),
                        Decimal(0))
            per_serving[n] = (total / servings).quantize(cent, rounding=ROUND_HALF_UP)
        new_id = conn.execute(food.insert().values(
            name=m["name"], unit="serving", basis_amount=1, serving_size=1, serving_label=None,
            recipe_servings=servings, notes=m["notes"], is_favourite=bool(m["is_favourite"]),
            created_at=m["created_at"] or now, updated_at=now, **per_serving,
        ).returning(food.c.id)).scalar_one()
        for l in lines:
            conn.execute(food_ingredient.insert().values(food_id=new_id, ingredient_id=l["id"], quantity=l["quantity"]))
        conn.execute(food_tag.insert().values(food_id=new_id, tag_id=meal_tag_id))


def downgrade():
    # Built foods only exist in this version, so they are removed; the old meals were never touched.
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM food_ingredient"))
    conn.execute(sa.text("DELETE FROM food_tag"))
    conn.execute(sa.text("DELETE FROM food WHERE recipe_servings IS NOT NULL"))
    with op.batch_alter_table('food', schema=None) as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('recipe_servings')
    op.drop_index('ix_food_ingredient_ingredient_id', table_name='food_ingredient')
    op.drop_index('ix_food_ingredient_food_id', table_name='food_ingredient')
    op.drop_table('food_ingredient')
    op.drop_table('food_tag')
    op.drop_table('tag')
