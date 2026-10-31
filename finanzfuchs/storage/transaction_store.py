"""Booked transactions with their assignment, and the record of every import."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from finanzfuchs.banking.transactions import BankTransaction
from finanzfuchs.ledger import AssignmentSource, LedgerEntry
from finanzfuchs.storage.money import from_cents, to_cents


@dataclass(frozen=True)
class ImportRecord:
    file_name: str
    account: str
    imported_at: datetime
    imported_by: str
    added_count: int
    skipped_count: int


class TransactionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def known_ids(self) -> set[str]:
        return {row[0] for row in self._connection.execute("SELECT id FROM transactions")}

    def add(self, transactions: list[BankTransaction], import_id: int) -> None:
        self._connection.executemany(
            """INSERT INTO transactions (id, account, booking_date, amount_cents,
                   counterparty_name, counterparty_iban, purpose, import_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [_insert_values(transaction, import_id) for transaction in transactions],
        )

    def entries(self) -> list[LedgerEntry]:
        rows = self._connection.execute("SELECT * FROM transactions ORDER BY booking_date, rowid")
        return [_to_entry(row) for row in rows]

    def get(self, transaction_id: str) -> LedgerEntry | None:
        row = self._connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        return _to_entry(row) if row else None

    def needing_attention(self) -> list[LedgerEntry]:
        """Open first, then doubtful, newest first within each group."""
        entries = [entry for entry in self.entries() if entry.needs_attention]
        return sorted(
            entries, key=lambda e: (not e.is_open, -e.transaction.booking_date.toordinal())
        )

    def assign(
        self, transaction_id: str, plan_line_id: str | None, source: AssignmentSource, note: str
    ) -> None:
        self._connection.execute(
            "UPDATE transactions SET plan_line_id = ?, source = ?, note = ? WHERE id = ?",
            (plan_line_id, source.value, note, transaction_id),
        )

    def record_import(self, record: ImportRecord) -> int:
        cursor = self._connection.execute(
            """INSERT INTO imports (file_name, account, imported_at, imported_by, added_count,
                   skipped_count) VALUES (?, ?, ?, ?, ?, ?)""",
            (record.file_name, record.account, record.imported_at.isoformat(),
             record.imported_by, record.added_count, record.skipped_count),
        )  # fmt: skip
        return int(cursor.lastrowid or 0)

    def latest_imports(self, limit: int) -> list[ImportRecord]:
        rows = self._connection.execute(
            "SELECT * FROM imports ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            ImportRecord(
                file_name=row["file_name"],
                account=row["account"],
                imported_at=datetime.fromisoformat(row["imported_at"]),
                imported_by=row["imported_by"],
                added_count=row["added_count"],
                skipped_count=row["skipped_count"],
            )
            for row in rows
        ]


def _insert_values(transaction: BankTransaction, import_id: int) -> tuple[object, ...]:
    return (
        transaction.transaction_id,
        transaction.account_uid,
        transaction.booking_date.isoformat(),
        to_cents(transaction.amount),
        transaction.counterparty_name,
        transaction.counterparty_iban,
        transaction.purpose,
        import_id,
    )


def _to_entry(row: sqlite3.Row) -> LedgerEntry:
    transaction = BankTransaction(
        transaction_id=row["id"],
        account_uid=row["account"],
        booking_date=date.fromisoformat(row["booking_date"]),
        amount=from_cents(row["amount_cents"]),
        counterparty_name=row["counterparty_name"],
        counterparty_iban=row["counterparty_iban"],
        purpose=row["purpose"],
        is_booked=True,
    )
    return LedgerEntry(
        transaction=transaction,
        plan_line_id=row["plan_line_id"],
        source=AssignmentSource(row["source"]),
        note=row["note"],
    )
