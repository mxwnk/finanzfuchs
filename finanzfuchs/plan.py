"""Plan lines: what the family intends to earn and spend, and since when."""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIXED = "fix"
VARIABLE = "variabel"
KINDS = (FIXED, VARIABLE)
INCOME_TYPE = "Einnahme"
YEARLY_RHYTHM = "Jahr"
FIXED_COSTS_POT = "Fixkosten"
# Categories whose lines are debited once a month at a known amount.
FIXED_CATEGORIES = frozenset({"Wohnen", "Versicherungen", "Fixkosten", "Sparen"})


class PlanFileError(ValueError):
    """The plan file contains a line that cannot be used."""


@dataclass(frozen=True)
class PlanLine:
    plan_line_id: str
    line_type: str
    """`Einnahme`, `Ausgabe` or `Umbuchung`."""
    category: str
    description: str
    amount: Decimal
    rhythm: str
    """`Monat` or `Jahr`: how often `amount` is due."""
    pot: str
    """The account or person a standing order sends the money to; empty for the joint account."""
    valid_from: date
    valid_until: date | None
    kind: str = VARIABLE
    """`fix` (arrives once at a known amount) or `variabel` (a budget used up over the month)."""

    @property
    def is_paid_from_fixed_costs_pot(self) -> bool:
        """Yearly costs and what the Fixkosten account reimburses are saved up, not monthly."""
        return self.rhythm == YEARLY_RHYTHM or self.pot == FIXED_COSTS_POT


def default_kind(line_type: str, category: str, pot: str) -> str:
    """The first guess for plan lines from before the field existed; editable on the plan page."""
    if line_type == INCOME_TYPE or pot or category in FIXED_CATEGORIES:
        return FIXED
    return VARIABLE


def load_plan(path: Path) -> list[PlanLine]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = enumerate(csv.DictReader(file), 2)
        return [_read_plan_line(row, line_number) for line_number, row in rows]


def _read_plan_line(row: dict[str, str], line_number: int) -> PlanLine:
    try:
        return PlanLine(
            plan_line_id=row["plan_line_id"],
            line_type=row["type"],
            category=row["category"],
            description=row["description"],
            amount=Decimal(row["amount"]),
            rhythm=row["rhythm"],
            pot=row["pot"],
            valid_from=date.fromisoformat(row["valid_from"]),
            valid_until=date.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
            kind=row.get("kind") or default_kind(row["type"], row["category"], row["pot"]),
        )
    except (KeyError, ValueError, InvalidOperation) as error:
        raise PlanFileError(f"Unusable plan line in line {line_number}: {error}") from error
