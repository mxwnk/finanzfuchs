"""The local journal of booked transactions, one CSV row per transaction.

Until the Google Sheet exists this file collects every import. Pending transactions are left out:
their details may still change, and they arrive again once they are booked.
"""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from bauplan.banking.transactions import BankTransaction

COLUMNS = (
    "transaction_id",
    "account_uid",
    "booking_date",
    "amount",
    "counterparty_name",
    "counterparty_iban",
    "purpose",
)


@dataclass(frozen=True)
class AddResult:
    added_count: int
    skipped_count: int
    pending_count: int


class TransactionLedger:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[BankTransaction]:
        if not self._path.exists():
            return []
        with self._path.open(newline="", encoding="utf-8") as file:
            return [_from_row(row) for row in csv.DictReader(file)]

    def add(self, candidates: list[BankTransaction]) -> AddResult:
        stored = self.load()
        known_ids = {transaction.transaction_id for transaction in stored}
        booked = [candidate for candidate in candidates if candidate.is_booked]
        new = [candidate for candidate in booked if candidate.transaction_id not in known_ids]
        self._write(sorted(stored + new, key=lambda transaction: transaction.booking_date))
        return AddResult(
            added_count=len(new),
            skipped_count=len(booked) - len(new),
            pending_count=len(candidates) - len(booked),
        )

    def _write(self, transactions: list[BankTransaction]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(_to_row(transaction) for transaction in transactions)


def _to_row(transaction: BankTransaction) -> dict[str, str]:
    return {
        "transaction_id": transaction.transaction_id,
        "account_uid": transaction.account_uid,
        "booking_date": transaction.booking_date.isoformat(),
        "amount": str(transaction.amount),
        "counterparty_name": transaction.counterparty_name,
        "counterparty_iban": transaction.counterparty_iban,
        "purpose": transaction.purpose,
    }


def _from_row(row: dict[str, str]) -> BankTransaction:
    return BankTransaction(
        transaction_id=row["transaction_id"],
        account_uid=row["account_uid"],
        booking_date=date.fromisoformat(row["booking_date"]),
        amount=Decimal(row["amount"]),
        counterparty_name=row["counterparty_name"],
        counterparty_iban=row["counterparty_iban"],
        purpose=row["purpose"],
        is_booked=True,
    )
