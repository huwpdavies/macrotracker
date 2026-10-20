"""Pull nutrition values out of text pasted from a supermarket label or website."""
import re

NUM = r"(\d+(?:[.,]\d+)?)"

# Each pattern is matched against the start of a line, so "of which saturates" is ignored.
LINE_PATTERNS = {
    "fat_g": r"(?:total\s+)?fat\b",
    "carbs_g": r"(?:total\s+)?carbohydrates?\b",
    "protein_g": r"protein\b",
    "fibre_g": r"(?:dietary\s+)?fi[bv]re?\b",
    "salt_g": r"salt\b",
}


def _first_number(text):
    match = re.search(NUM, text)
    return float(match.group(1).replace(",", ".")) if match else None


def parse_label(raw):
    """Return {"values": {field: number}, "missing": [field, ...]}.

    Only fields that were found are in "values". When a table has both
    "per 100g" and "per serving" columns, the first number on each line wins.
    """
    values = {}
    per = re.search(r"per\s*" + NUM + r"\s*(g|ml)\b", raw, re.I)
    if per:
        values["basis_amount"] = float(per.group(1).replace(",", "."))
        values["unit"] = per.group(2).lower()

    for line in re.split(r"[\n\r]+", raw):
        line = line.strip()
        if not line:
            continue
        lowered = line.lower()
        if "calories_kcal" not in values:
            kcal = re.search(NUM + r"\s*kcal", line, re.I)
            if kcal:
                values["calories_kcal"] = float(kcal.group(1).replace(",", "."))
                continue
            if re.match(r"calories?\b", lowered):
                number = _first_number(line)
                if number is not None:
                    values["calories_kcal"] = number
                    continue
        for field, pattern in LINE_PATTERNS.items():
            if field not in values and re.match(pattern, lowered):
                number = _first_number(line)
                if number is not None:
                    values[field] = number
                break

    wanted = ["calories_kcal", *LINE_PATTERNS]
    return {"values": values, "missing": [f for f in wanted if f not in values]}
