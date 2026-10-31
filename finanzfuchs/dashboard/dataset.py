"""The data the dashboard page computes on: plan lines and transactions with their assignment.

All aggregation happens in the page, so every filter is instant.
"""

from datetime import datetime
from typing import Any

from finanzfuchs.ledger import LedgerEntry
from finanzfuchs.plan import PlanLine

YEARLY_RHYTHM = "Jahr"
MONTHS_PER_YEAR = 12


def build_dataset(
    plan: list[PlanLine], entries: list[LedgerEntry], generated_at: datetime
) -> dict[str, Any]:
    return {
        "generatedAt": generated_at.isoformat(),
        "plan": [_plan_line(line) for line in plan],
        "transactions": [_transaction(entry) for entry in entries],
    }


def monthly_amount(line: PlanLine) -> float:
    amount = float(line.amount)
    return amount / MONTHS_PER_YEAR if line.rhythm == YEARLY_RHYTHM else amount


def _plan_line(line: PlanLine) -> dict[str, Any]:
    return {
        "id": line.plan_line_id,
        "type": line.line_type,
        "category": line.category,
        "description": line.description,
        "monthly": monthly_amount(line),
        "pot": line.pot,
        "validFrom": line.valid_from.isoformat(),
        "validUntil": line.valid_until.isoformat() if line.valid_until else None,
    }


def _transaction(entry: LedgerEntry) -> dict[str, Any]:
    transaction = entry.transaction
    return {
        "id": transaction.transaction_id,
        "date": transaction.booking_date.isoformat(),
        "amount": float(transaction.amount),
        "counterparty": transaction.counterparty_name,
        "purpose": transaction.purpose,
        "line": entry.plan_line_id or "",
        "source": entry.source.value,
        "note": entry.note,
    }
