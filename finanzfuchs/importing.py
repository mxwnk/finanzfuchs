"""Bringing a DKB export into the database and assigning what the rules know."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from finanzfuchs.assignment.service import apply_rules
from finanzfuchs.imports.dkb_csv import parse_dkb_export
from finanzfuchs.ledger import AssignmentSource, LedgerEntry
from finanzfuchs.storage.transaction_store import ImportRecord, TransactionStore


@dataclass(frozen=True)
class ImportSummary:
    file_name: str
    added_count: int
    skipped_count: int
    pending_count: int
    assigned_count: int

    @property
    def waiting_count(self) -> int:
        return self.added_count - self.assigned_count


def import_dkb_export(
    connection: sqlite3.Connection, text: str, file_name: str, imported_by: str, now: datetime
) -> ImportSummary:
    export = parse_dkb_export(text)
    booked = [transaction for transaction in export.transactions if transaction.is_booked]
    store = TransactionStore(connection)
    known_ids = store.known_ids()
    new = [transaction for transaction in booked if transaction.transaction_id not in known_ids]
    record = ImportRecord(
        file_name=file_name,
        account=export.account_iban,
        imported_at=now,
        imported_by=imported_by,
        added_count=len(new),
        skipped_count=len(booked) - len(new),
    )
    store.add(new, store.record_import(record))
    entries = [LedgerEntry(t, None, AssignmentSource.OPEN, "") for t in new]
    return ImportSummary(
        file_name=file_name,
        added_count=len(new),
        skipped_count=record.skipped_count,
        pending_count=len(export.transactions) - len(booked),
        assigned_count=apply_rules(connection, entries),
    )
