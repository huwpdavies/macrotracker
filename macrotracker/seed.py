import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Food, Goal, Meal, MealItem


@click.command("seed")
@with_appcontext
def seed_command():
    """Add sample foods, a meal and two goals (only if the database is empty)."""
    if Food.query.first() or Goal.query.first():
        click.echo("Database already has data; nothing seeded.")
        return

    tuna = Food(name="Tesco tuna chunks 105g can", calories_kcal=110, unit="g", basis_amount=100,
                protein_g=25, carbs_g=0, fat_g=1, salt_g=1, fibre_g=0,
                serving_size=105, serving_label="1 can")
    avocado = Food(name="Avocado", calories_kcal=250, unit="unit", basis_amount=1,
                   protein_g=2.5, carbs_g=12, fat_g=22, salt_g=0.02, fibre_g=10,
                   serving_size=0.5, serving_label="1/2 avocado")
    oats = Food(name="Porridge oats", calories_kcal=372, unit="g", basis_amount=100,
                protein_g=11, carbs_g=60, fat_g=8, salt_g=0.02, fibre_g=9,
                serving_size=40, serving_label="1 bowl (40 g)")
    egg = Food(name="Egg", calories_kcal=78, unit="unit", basis_amount=1,
               protein_g=6.3, carbs_g=0.4, fat_g=5, salt_g=0.35, fibre_g=0,
               serving_size=1, serving_label="1 egg")
    db.session.add_all([tuna, avocado, oats, egg])
    db.session.flush()  # gives each food an id so the meal items can point at them

    lunch = Meal(name="Tuna and avocado lunch", notes="Quick high-protein lunch")
    lunch.items = [
        MealItem(food=tuna, quantity=105),
        MealItem(food=avocado, quantity=0.5),
    ]
    db.session.add(lunch)

    db.session.add_all([
        Goal(name="Maintain", calories_kcal=2200, protein_g=130, carbs_g=250, fat_g=70,
             salt_g=6, fibre_g=30, is_active=True),
        Goal(name="Cut", calories_kcal=1800, protein_g=160, carbs_g=180, fat_g=55,
             salt_g=6, fibre_g=35, is_active=False),
    ])
    db.session.commit()
    click.echo("Seeded 4 foods, 1 meal and 2 goals.")
