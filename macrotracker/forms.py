from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

MACRO_FIELDS = [
    ("protein_g", "Protein (g)"),
    ("carbs_g", "Carbohydrates (g)"),
    ("fat_g", "Fat (g)"),
    ("salt_g", "Salt (g)"),
    ("fibre_g", "Fibre (g)"),
]


def _macro(label):
    return DecimalField(label, default=0, places=None,
                        validators=[Optional(), NumberRange(min=0, max=100000)])


class FoodForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    brand = StringField("Brand (optional)", validators=[Optional(), Length(max=100)])
    unit = SelectField("Unit")
    basis_amount = DecimalField("Nutrition values are per", default=100, places=None,
                                validators=[DataRequired(), NumberRange(min=0.01, max=100000)])
    protein_g = _macro("Protein (g)")
    carbs_g = _macro("Carbohydrates (g)")
    fat_g = _macro("Fat (g)")
    salt_g = _macro("Salt (g)")
    fibre_g = _macro("Fibre (g)")
    serving_size = DecimalField("Typical serving size", places=None,
                                validators=[DataRequired(), NumberRange(min=0.01, max=100000)])
    serving_label = StringField("Serving label (optional, e.g. 1 can)",
                                validators=[Optional(), Length(max=100)])
