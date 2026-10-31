"""Turns raw Enable Banking transactions into the values Bauplan works with."""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

DEBIT_INDICATOR = "DBIT"
CREDIT_INDICATOR = "CRDT"
BOOKED_STATUS = "BOOK"
DERIVED_ID_PREFIX = "derived-"


class TransactionParseError(ValueError):
    """A transaction from the bank lacks a field Bauplan cannot do without."""


@dataclass(frozen=True)
class BankTransaction:
    transaction_id: str
    account_uid: str
    booking_date: date
    amount: Decimal
    """Negative for money leaving the account, positive for money arriving."""
    counterparty_name: str
    counterparty_iban: str
    purpose: str
    is_booked: bool


def parse_transaction(raw: dict[str, Any], account_uid: str) -> BankTransaction:
    is_debit = _is_debit(raw)
    counterparty_role = "creditor" if is_debit else "debtor"
    unsigned_amount = _read_amount(raw)
    booking_date = _read_booking_date(raw)
    purpose = _join_purpose(raw)
    counterparty_name = _read_name(raw.get(counterparty_role))
    counterparty_iban = _read_iban(raw.get(f"{counterparty_role}_account"))
    amount = -unsigned_amount if is_debit else unsigned_amount

    return BankTransaction(
        transaction_id=_read_identity(raw, account_uid, booking_date, amount, purpose),
        account_uid=account_uid,
        booking_date=booking_date,
        amount=amount,
        counterparty_name=counterparty_name,
        counterparty_iban=counterparty_iban,
        purpose=purpose,
        is_booked=raw.get("status") == BOOKED_STATUS,
    )


def _is_debit(raw: dict[str, Any]) -> bool:
    indicator = raw.get("credit_debit_indicator")
    if indicator not in (DEBIT_INDICATOR, CREDIT_INDICATOR):
        raise TransactionParseError(
            f"Unknown credit_debit_indicator {indicator!r} in transaction {_describe(raw)}"
        )
    return indicator == DEBIT_INDICATOR


def _read_amount(raw: dict[str, Any]) -> Decimal:
    transaction_amount = raw.get("transaction_amount") or {}
    try:
        return abs(Decimal(str(transaction_amount["amount"])))
    except (KeyError, InvalidOperation) as error:
        raise TransactionParseError(
            f"Missing or invalid transaction_amount in transaction {_describe(raw)}"
        ) from error


def _read_booking_date(raw: dict[str, Any]) -> date:
    date_text = raw.get("booking_date") or raw.get("value_date")
    if not date_text:
        raise TransactionParseError(f"No booking or value date in transaction {_describe(raw)}")
    return date.fromisoformat(date_text)


def _join_purpose(raw: dict[str, Any]) -> str:
    lines = raw.get("remittance_information") or []
    return " ".join(line.strip() for line in lines if line.strip())


def _read_name(party: dict[str, Any] | None) -> str:
    return (party or {}).get("name") or ""


def _read_iban(account: dict[str, Any] | None) -> str:
    return (account or {}).get("iban") or ""


def _read_identity(
    raw: dict[str, Any], account_uid: str, booking_date: date, amount: Decimal, purpose: str
) -> str:
    bank_reference = raw.get("transaction_id") or raw.get("entry_reference")
    if bank_reference:
        return str(bank_reference)
    return _derive_identity(account_uid, booking_date, amount, purpose)


def _derive_identity(account_uid: str, booking_date: date, amount: Decimal, purpose: str) -> str:
    """Some banks send no reference; the same booking must still map to the same row."""
    fingerprint = f"{account_uid}|{booking_date.isoformat()}|{amount}|{purpose}"
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"{DERIVED_ID_PREFIX}{digest}"


def _describe(raw: dict[str, Any]) -> str:
    return str(raw.get("transaction_id") or raw.get("entry_reference") or "<without reference>")
