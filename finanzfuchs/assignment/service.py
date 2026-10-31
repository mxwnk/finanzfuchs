"""Assigning transactions: by the rules after an import, or by hand in the app."""

import sqlite3
from dataclasses import dataclass

from finanzfuchs.assignment.rules import AssignmentRule, assign
from finanzfuchs.ledger import AssignmentSource, LedgerEntry
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.rule_store import RuleStore
from finanzfuchs.storage.transaction_store import TransactionStore


class AssignmentError(ValueError):
    """The transaction or plan line does not exist."""


@dataclass(frozen=True)
class HandAssignment:
    rule_created: bool
    also_assigned: int
    """Other transactions the remembered rule took care of right away."""


def apply_rules(connection: sqlite3.Connection, entries: list[LedgerEntry]) -> int:
    """Assigns the given entries by the stored rules; returns how many got a plan line."""
    rules = [stored.rule for stored in RuleStore(connection).rules()]
    store = TransactionStore(connection)
    assigned = 0
    for result in assign([entry.transaction for entry in entries], rules):
        if result.plan_line_id is None:
            continue
        store.assign(result.transaction.transaction_id, result.plan_line_id,
                     AssignmentSource.RULE, result.note)  # fmt: skip
        assigned += 1
    return assigned


def assign_by_hand(
    connection: sqlite3.Connection, transaction_id: str, plan_line_id: str, remember: bool
) -> HandAssignment:
    """`remember` turns the choice into a rule for the same counterparty and applies it."""
    entry = _existing_entry(connection, transaction_id)
    _ensure_plan_line_exists(connection, plan_line_id)
    TransactionStore(connection).assign(transaction_id, plan_line_id, AssignmentSource.MANUAL, "")
    if not remember or not entry.transaction.counterparty_name.strip():
        return HandAssignment(rule_created=False, also_assigned=0)
    RuleStore(connection).add_at_top(_rule_for_counterparty(entry, plan_line_id))
    return HandAssignment(rule_created=True, also_assigned=_apply_to_waiting(connection))


def confirm(connection: sqlite3.Connection, transaction_id: str) -> None:
    """Accepts the rule's guess for a doubtful transaction as if it was chosen by hand."""
    entry = _existing_entry(connection, transaction_id)
    if entry.plan_line_id is None:
        raise AssignmentError(f"Transaction {transaction_id} has no plan line to confirm")
    TransactionStore(connection).assign(
        transaction_id, entry.plan_line_id, AssignmentSource.MANUAL, ""
    )


def _apply_to_waiting(connection: sqlite3.Connection) -> int:
    waiting = [e for e in TransactionStore(connection).entries() if e.may_be_reassigned_by_rule]
    return apply_rules(connection, waiting)


def _rule_for_counterparty(entry: LedgerEntry, plan_line_id: str) -> AssignmentRule:
    direction = "out" if entry.transaction.amount < 0 else "in"
    return AssignmentRule(
        plan_line_id=plan_line_id,
        counterparty_contains=entry.transaction.counterparty_name.strip(),
        direction=direction,
        note="In der App gemerkt",
    )


def _existing_entry(connection: sqlite3.Connection, transaction_id: str) -> LedgerEntry:
    entry = TransactionStore(connection).get(transaction_id)
    if entry is None:
        raise AssignmentError(f"Unknown transaction {transaction_id}")
    return entry


def _ensure_plan_line_exists(connection: sqlite3.Connection, plan_line_id: str) -> None:
    if PlanStore(connection).get(plan_line_id) is None:
        raise AssignmentError(f"Unknown plan line {plan_line_id}")
