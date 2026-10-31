"""Reads the CSV export of the DKB online banking ("Umsatzliste")."""

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from bauplan.banking.transactions import BankTransaction

COLUMN_HEADER_MARKER = "Buchungsdatum"
BOOKED_STATUS = "Gebucht"
DATE_FORMAT = "%d.%m.%y"
ID_PREFIX = "dkb-"
DELIMITER = ";"


class DkbExportError(ValueError):
    """The file is not a DKB export Bauplan understands."""


@dataclass(frozen=True)
class DkbExport:
    account_iban: str
    transactions: list[BankTransaction]


def parse_dkb_export(text: str) -> DkbExport:
    lines = text.lstrip("﻿").splitlines()
    account_iban = _read_account_iban(lines)
    header_index = _find_column_header(lines)
    rows = csv.DictReader(lines[header_index:], delimiter=DELIMITER)
    seen_fingerprints: Counter[str] = Counter()
    transactions = [
        _parse_row(row, account_iban, header_index + offset + 2, seen_fingerprints)
        for offset, row in enumerate(rows)
    ]
    return DkbExport(account_iban=account_iban, transactions=transactions)


def _read_account_iban(lines: list[str]) -> str:
    first_line = next(csv.reader(lines[:1], delimiter=DELIMITER), [])
    if len(first_line) < 2 or not first_line[1]:
        raise DkbExportError("The first line does not name the account IBAN")
    return first_line[1].replace(" ", "")


def _find_column_header(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.startswith(f'"{COLUMN_HEADER_MARKER}"'):
            return index
    raise DkbExportError(f"No column header starting with {COLUMN_HEADER_MARKER!r} found")


def _parse_row(
    row: dict[str, str], account_iban: str, line_number: int, seen_fingerprints: Counter[str]
) -> BankTransaction:
    try:
        amount = _parse_amount(row["Betrag (€)"])
        booking_date = datetime.strptime(row["Buchungsdatum"], DATE_FORMAT).date()
    except (KeyError, ValueError, InvalidOperation) as error:
        raise DkbExportError(f"Unreadable row in line {line_number}: {error}") from error

    is_payment = amount < 0
    counterparty_name = row["Zahlungsempfänger*in"] if is_payment else row["Zahlungspflichtige*r"]
    counterparty_iban = row["IBAN"].replace(" ", "")
    purpose = " ".join(row["Verwendungszweck"].split())
    fingerprint = "|".join(
        [
            account_iban,
            booking_date.isoformat(),
            counterparty_name,
            counterparty_iban,
            purpose,
            str(amount),
            row.get("Kundenreferenz", ""),
        ]
    )

    return BankTransaction(
        transaction_id=_identify(fingerprint, seen_fingerprints),
        account_uid=account_iban,
        booking_date=booking_date,
        amount=amount,
        counterparty_name=counterparty_name.strip(),
        counterparty_iban=counterparty_iban,
        purpose=purpose,
        is_booked=row["Status"] == BOOKED_STATUS,
    )


def _parse_amount(text: str) -> Decimal:
    normalized = text.replace(" ", "").replace(".", "").replace(",", ".").strip()
    return Decimal(normalized).quantize(Decimal("0.01"))


def _identify(fingerprint: str, seen_fingerprints: Counter[str]) -> str:
    """The export has no ids; identical rows on one day are told apart by their order.

    Exports always cover whole days, so the order of identical rows is stable between exports.
    """
    occurrence = seen_fingerprints[fingerprint]
    seen_fingerprints[fingerprint] += 1
    digest = hashlib.sha256(f"{fingerprint}|{occurrence}".encode()).hexdigest()[:16]
    return f"{ID_PREFIX}{digest}"
