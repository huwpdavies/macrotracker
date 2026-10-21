"""All "what day is it?" questions go through here, so the day boundary is
always midnight in London, never midnight UTC (which is 1 am in summer)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")


def today_london(now=None):
    """Today's date in London. `now` (an aware datetime) is only passed by tests."""
    now = now or datetime.now(LONDON)
    return now.astimezone(LONDON).date()


def parse_day(text):
    """'2026-10-21' -> date, or None if it isn't a real date."""
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def day_label(day, today=None):
    today = today or today_london()
    names = {today: "Today", today - timedelta(days=1): "Yesterday", today + timedelta(days=1): "Tomorrow"}
    return names.get(day, f"{day:%A} {day.day} {day:%B}")


def long_date(day):
    return f"{day:%A} {day.day} {day:%B %Y}"
