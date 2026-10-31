from datetime import date
from decimal import Decimal
from pathlib import Path

from bauplan.banking.transactions import BankTransaction
from bauplan.ledger import TransactionLedger


def transaction(transaction_id: str, booking_date: date = date(2026, 3, 2)) -> BankTransaction:
    return BankTransaction(
        transaction_id=transaction_id,
        account_uid="DE01",
        booking_date=booking_date,
        amount=Decimal("-61.07"),
        counterparty_name="Sky; Deutschland",
        counterparty_iban="DE11",
        purpose='Sky "Abo"',
        is_booked=True,
    )


def test_an_empty_ledger_has_no_transactions(tmp_path: Path) -> None:
    ledger = TransactionLedger(tmp_path / "transactions.csv")

    assert ledger.load() == []


def test_returns_added_transactions_unchanged(tmp_path: Path) -> None:
    ledger = TransactionLedger(tmp_path / "transactions.csv")

    ledger.add([transaction("a")])

    assert ledger.load() == [transaction("a")]


def test_skips_transactions_it_already_holds(tmp_path: Path) -> None:
    ledger = TransactionLedger(tmp_path / "transactions.csv")
    ledger.add([transaction("a")])

    result = ledger.add([transaction("a"), transaction("b")])

    assert result.added_count == 1
    assert result.skipped_count == 1
    assert [stored.transaction_id for stored in ledger.load()] == ["a", "b"]


def test_skips_pending_transactions_until_they_are_booked(tmp_path: Path) -> None:
    ledger = TransactionLedger(tmp_path / "transactions.csv")
    pending = BankTransaction(**{**transaction("p").__dict__, "is_booked": False})

    result = ledger.add([pending])

    assert result.pending_count == 1
    assert ledger.load() == []


def test_keeps_the_ledger_sorted_by_booking_date(tmp_path: Path) -> None:
    ledger = TransactionLedger(tmp_path / "transactions.csv")

    ledger.add([transaction("late", date(2026, 5, 1)), transaction("early", date(2026, 1, 2))])

    assert [stored.transaction_id for stored in ledger.load()] == ["early", "late"]
