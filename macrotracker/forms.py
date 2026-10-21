from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


def _nutrient(label):
    return DecimalField(label, default=0, places=None,
                        validators=[Optional(), NumberRange(min=0, max=100000)])


class FoodForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    basis_amount = DecimalField("Per", default=100, places=None,
                                validators=[DataRequired(), NumberRange(min=0.01, max=100000)])
    unit = SelectField("Unit")
    calories_kcal = _nutrient("Calories (kcal)")
    protein_g = _nutrient("Protein (g)")
    carbs_g = _nutrient("Carbs (g)")
    fat_g = _nutrient("Fat (g)")
    fibre_g = _nutrient("Fibre (g)")
    salt_g = _nutrient("Salt (g)")
    serving_size = DecimalField("Size", places=None,
                                validators=[DataRequired(), NumberRange(min=0.01, max=100000)])
    serving_label = StringField("Label (optional)",
                                validators=[Optional(), Length(max=100)])


class MealForm(FlaskForm):
    # The ingredient rows are variable-length, so the route reads them straight from request.form.
    name = StringField("Meal name", validators=[DataRequired(), Length(max=200)])
    servings = DecimalField("Servings this makes", default=1, places=None,
                            validators=[DataRequired(), NumberRange(min=0.01, max=1000)])
    notes = StringField("Notes (optional)", validators=[Optional(), Length(max=500)])
