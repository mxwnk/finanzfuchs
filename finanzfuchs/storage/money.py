"""Amounts are stored as whole cents: SQLite has no decimal type and floats round."""

from decimal import ROUND_HALF_UP, Decimal

CENTS_PER_EURO = 100


def to_cents(amount: Decimal) -> int:
    return int((amount * CENTS_PER_EURO).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / CENTS_PER_EURO).quantize(Decimal("0.01"))
