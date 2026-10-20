from macrotracker.services.label_parser import parse_label

TESCO = """Typical values per 100g
Energy 1046kJ / 250kcal
Fat 10g
of which saturates 3.1g
Carbohydrate 5.2g
of which sugars 1.0g
Fibre 2.5g
Protein 30g
Salt 1.2g"""


def test_parses_a_typical_label():
    out = parse_label(TESCO)
    assert out["values"] == {
        "basis_amount": 100, "unit": "g", "calories_kcal": 250, "fat_g": 10,
        "carbs_g": 5.2, "fibre_g": 2.5, "protein_g": 30, "salt_g": 1.2,
    }
    assert out["missing"] == []


def test_first_column_wins_in_tab_separated_table():
    out = parse_label("Per 100ml\nProtein\t3.4g\t8.5g\nCalories 64")
    assert out["values"]["protein_g"] == 3.4
    assert out["values"]["unit"] == "ml"
    assert out["values"]["calories_kcal"] == 64


def test_unrecognised_text_finds_nothing():
    assert parse_label("hello world")["values"] == {}
