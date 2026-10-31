"""Rules that assign a transaction to a plan line; the first matching rule wins.

The rule file is kept by hand (or by Claude Code) until v2 assigns through the Claude API.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bauplan.banking.transactions import BankTransaction

Direction = Literal["in", "out", ""]


class RuleFileError(ValueError):
    """The rule file contains a rule that cannot be used."""


@dataclass(frozen=True)
class AssignmentRule:
    plan_line_id: str
    counterparty_contains: str = ""
    purpose_contains: str = ""
    counterparty_iban: str = ""
    direction: Direction = ""
    note: str = ""
    """Shown next to the assignment; `ZWEIFEL: …` marks a guess that needs an answer."""

    def __post_init__(self) -> None:
        if not (self.counterparty_contains or self.purpose_contains or self.counterparty_iban):
            raise ValueError(f"Rule for {self.plan_line_id!r} needs at least one condition")

    def matches(self, transaction: BankTransaction) -> bool:
        return (
            _contains(transaction.counterparty_name, self.counterparty_contains)
            and _contains(transaction.purpose, self.purpose_contains)
            and _has_iban(transaction, self.counterparty_iban)
            and _has_direction(transaction, self.direction)
        )


@dataclass(frozen=True)
class Assignment:
    transaction: BankTransaction
    plan_line_id: str | None
    rule_number: int | None
    """1-based position of the matching rule, so a wrong assignment leads to its rule."""
    note: str = ""


def assign(transactions: list[BankTransaction], rules: list[AssignmentRule]) -> list[Assignment]:
    return [_assign_one(transaction, rules) for transaction in transactions]


def load_rules(path: Path) -> list[AssignmentRule]:
    with path.open(newline="", encoding="utf-8") as file:
        return [
            _read_rule(row, line_number) for line_number, row in enumerate(csv.DictReader(file), 2)
        ]


def _assign_one(transaction: BankTransaction, rules: list[AssignmentRule]) -> Assignment:
    for rule_number, rule in enumerate(rules, 1):
        if rule.matches(transaction):
            return Assignment(transaction, rule.plan_line_id, rule_number, rule.note)
    return Assignment(transaction, None, None)


def _read_rule(row: dict[str, str], line_number: int) -> AssignmentRule:
    try:
        return AssignmentRule(
            plan_line_id=row["plan_line_id"].strip(),
            counterparty_contains=row["counterparty_contains"].strip(),
            purpose_contains=row["purpose_contains"].strip(),
            counterparty_iban=row["counterparty_iban"].strip(),
            direction=_read_direction(row["direction"].strip()),
            note=(row.get("note") or "").strip(),
        )
    except (KeyError, ValueError) as error:
        raise RuleFileError(f"Unusable rule in line {line_number}: {error}") from error


def _read_direction(text: str) -> Direction:
    if text not in ("in", "out", ""):
        raise ValueError(f"direction must be 'in', 'out' or empty, got {text!r}")
    return text  # type: ignore[return-value]


def _contains(text: str, fragment: str) -> bool:
    return not fragment or fragment.casefold() in text.casefold()


def _has_iban(transaction: BankTransaction, iban: str) -> bool:
    return not iban or transaction.counterparty_iban == iban


def _has_direction(transaction: BankTransaction, direction: Direction) -> bool:
    if direction == "out":
        return transaction.amount < 0
    if direction == "in":
        return transaction.amount > 0
    return True
