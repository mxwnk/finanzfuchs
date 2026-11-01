"""German number formats for the templates: `1.234 €`, `1.234,56 €`, `42 %`."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def euro(amount: Decimal | float | int, cents: bool = False) -> str:
    places = Decimal("0.01") if cents else Decimal(1)
    rounded = Decimal(str(amount)).quantize(places, rounding=ROUND_HALF_UP)
    text = f"{abs(rounded):,.2f}" if cents else f"{abs(rounded):,.0f}"
    german = text.replace(",", " ").replace(".", ",").replace(" ", ".")
    sign = "−" if rounded < 0 else ""
    return f"{sign}{german} €"


def percent(share: Decimal | float) -> str:
    rounded = (Decimal(str(share)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{rounded} %"


def short_date(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]}, {day.day:02d}.{day.month:02d}."


def long_date(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}.{day.year}"
