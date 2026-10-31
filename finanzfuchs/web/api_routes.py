"""JSON endpoints behind the assigning page."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from finanzfuchs.assignment.service import AssignmentError, assign_by_hand, confirm
from finanzfuchs.ledger import LedgerEntry
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.transaction_store import TransactionStore
from finanzfuchs.web.context import ApiUser, Context

router = APIRouter(prefix="/api")


class AssignRequest(BaseModel):
    plan_line_id: str
    remember: bool = False


@router.get("/attention")
def attention(user: ApiUser, context: Context) -> dict[str, Any]:
    with context.database.connect() as connection:
        entries = TransactionStore(connection).needing_attention()
        plan = PlanStore(connection).list()
    return {
        "entries": [_entry_json(entry) for entry in entries],
        "planLines": [
            {
                "id": line.plan_line_id,
                "description": line.description,
                "category": line.category,
                "type": line.line_type,
            }  # fmt: skip
            for line in plan
        ],
    }


@router.post("/transactions/{transaction_id}/assign")
def assign(
    transaction_id: str,
    request: AssignRequest,
    user: ApiUser,
    context: Context,
) -> dict[str, Any]:
    with context.database.connect() as connection:
        try:
            result = assign_by_hand(
                connection, transaction_id, request.plan_line_id, request.remember
            )
        except AssignmentError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        remaining = len(TransactionStore(connection).needing_attention())
    return {"ruleCreated": result.rule_created, "alsoAssigned": result.also_assigned,
            "remaining": remaining}  # fmt: skip


@router.post("/transactions/{transaction_id}/confirm")
def confirm_guess(
    transaction_id: str,
    user: ApiUser,
    context: Context,
) -> dict[str, Any]:
    with context.database.connect() as connection:
        try:
            confirm(connection, transaction_id)
        except AssignmentError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        remaining = len(TransactionStore(connection).needing_attention())
    return {"remaining": remaining}


def _entry_json(entry: LedgerEntry) -> dict[str, Any]:
    transaction = entry.transaction
    return {
        "id": transaction.transaction_id,
        "date": transaction.booking_date.isoformat(),
        "amount": float(transaction.amount),
        "counterparty": transaction.counterparty_name,
        "purpose": transaction.purpose,
        "line": entry.plan_line_id or "",
        "note": entry.note,
        "isOpen": entry.is_open,
    }
