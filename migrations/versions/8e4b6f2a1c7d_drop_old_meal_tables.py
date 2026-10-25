"""Drop the old meal and meal_item tables.

Meals became built foods in 5d2a8c1f9b3e, which copied every meal across and left these
tables in place only so the previously deployed version kept working. Nothing reads them now.
Going back down recreates the tables empty; their old rows are in the JSON backup taken
before this ran (backups/before-dropping-meal-tables-*.json).

Revision ID: 8e4b6f2a1c7d
Revises: 5d2a8c1f9b3e
Create Date: 2026-10-25

"""
from alembic import op
import sqlalchemy as sa


revision = '8e4b6f2a1c7d'
down_revision = '5d2a8c1f9b3e'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('meal_item')   # first: it points at meal
    op.drop_table('meal')


def downgrade():
    op.create_table(
        'meal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('servings', sa.Numeric(precision=8, scale=2), server_default=sa.text('1'), nullable=False),
        sa.Column('is_favourite', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'meal_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meal_id', sa.Integer(), sa.ForeignKey('meal.id', ondelete='CASCADE'), nullable=False),
        sa.Column('food_id', sa.Integer(), sa.ForeignKey('food.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
