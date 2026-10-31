from datetime import date
from decimal import Decimal

import pytest

from finanzfuchs.banking.transactions import TransactionParseError, parse_transaction

ACCOUNT_UID = "account-uid-1"


def raw_debit(**overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "transaction_id": "tx-1",
        "entry_reference": "ref-1",
        "transaction_amount": {"currency": "EUR", "amount": "61.07"},
        "credit_debit_indicator": "DBIT",
        "status": "BOOK",
        "booking_date": "2026-03-02",
        "value_date": "2026-03-02",
        "creditor": {"name": "Sky Deutschland"},
        "creditor_account": {"iban": "DE11111111111111111111"},
        "debtor": {"name": "Max und Merle"},
        "debtor_account": {"iban": "DE22222222222222222222"},
        "remittance_information": ["Sky Abo", "Kd-Nr 4711"],
    }
    raw.update(overrides)
    return raw


def test_debit_becomes_negative_amount_with_creditor_as_counterparty() -> None:
    transaction = parse_transaction(raw_debit(), ACCOUNT_UID)

    assert transaction.amount == Decimal("-61.07")
    assert transaction.counterparty_name == "Sky Deutschland"
    assert transaction.counterparty_iban == "DE11111111111111111111"


def test_credit_becomes_positive_amount_with_debtor_as_counterparty() -> None:
    raw = raw_debit(
        credit_debit_indicator="CRDT",
        creditor={"name": "Max und Merle"},
        creditor_account={"iban": "DE22222222222222222222"},
        debtor={"name": "Arbeitgeber GmbH"},
        debtor_account={"iban": "DE33333333333333333333"},
    )

    transaction = parse_transaction(raw, ACCOUNT_UID)

    assert transaction.amount == Decimal("61.07")
    assert transaction.counterparty_name == "Arbeitgeber GmbH"
    assert transaction.counterparty_iban == "DE33333333333333333333"


def test_purpose_joins_all_remittance_lines() -> None:
    transaction = parse_transaction(raw_debit(), ACCOUNT_UID)

    assert transaction.purpose == "Sky Abo Kd-Nr 4711"


def test_keeps_account_dates_and_booking_status() -> None:
    transaction = parse_transaction(raw_debit(), ACCOUNT_UID)

    assert transaction.account_uid == ACCOUNT_UID
    assert transaction.booking_date == date(2026, 3, 2)
    assert transaction.is_booked


def test_pending_transaction_is_not_booked() -> None:
    transaction = parse_transaction(raw_debit(status="PDNG"), ACCOUNT_UID)

    assert not transaction.is_booked


def test_uses_transaction_id_as_identity() -> None:
    transaction = parse_transaction(raw_debit(), ACCOUNT_UID)

    assert transaction.transaction_id == "tx-1"


def test_falls_back_to_entry_reference_without_transaction_id() -> None:
    transaction = parse_transaction(raw_debit(transaction_id=None), ACCOUNT_UID)

    assert transaction.transaction_id == "ref-1"


def test_derives_stable_identity_when_the_bank_sends_no_reference() -> None:
    raw = raw_debit(transaction_id=None, entry_reference=None)

    first = parse_transaction(raw, ACCOUNT_UID)
    second = parse_transaction(dict(raw), ACCOUNT_UID)

    assert first.transaction_id == second.transaction_id
    assert first.transaction_id.startswith("derived-")


def test_falls_back_to_value_date_without_booking_date() -> None:
    transaction = parse_transaction(raw_debit(booking_date=None), ACCOUNT_UID)

    assert transaction.booking_date == date(2026, 3, 2)


def test_tolerates_missing_counterparty_and_purpose() -> None:
    raw = raw_debit(creditor=None, creditor_account=None, remittance_information=None)

    transaction = parse_transaction(raw, ACCOUNT_UID)

    assert transaction.counterparty_name == ""
    assert transaction.counterparty_iban == ""
    assert transaction.purpose == ""


def test_rejects_unknown_credit_debit_indicator() -> None:
    with pytest.raises(TransactionParseError, match="credit_debit_indicator"):
        parse_transaction(raw_debit(credit_debit_indicator="XXXX"), ACCOUNT_UID)


def test_rejects_transaction_without_amount() -> None:
    with pytest.raises(TransactionParseError, match="tx-1"):
        parse_transaction(raw_debit(transaction_amount=None), ACCOUNT_UID)
