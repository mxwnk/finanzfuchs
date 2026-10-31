import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from finanzfuchs.archive import RawArchive
from finanzfuchs.sync import SessionAccount, fetch_all_accounts, read_session_accounts

NOW = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
HISTORY_START = date(2026, 1, 1)


def raw_transaction(transaction_id: str, booking_date: str, status: str = "BOOK") -> dict:
    return {
        "transaction_id": transaction_id,
        "transaction_amount": {"currency": "EUR", "amount": "10.00"},
        "credit_debit_indicator": "DBIT",
        "status": status,
        "booking_date": booking_date,
    }


class FakeBank:
    def __init__(self, pages_by_account: dict[str, list[dict]]) -> None:
        self._pages_by_account = pages_by_account
        self.requested_starts: list[date] = []

    def fetch_transaction_pages(self, account_uid: str, date_from: date) -> list[dict]:
        self.requested_starts.append(date_from)
        return self._pages_by_account[account_uid]

    def fetch_balances(self, account_uid: str) -> dict:
        return {"balances": [{"balance_amount": {"amount": "100.00", "currency": "EUR"}}]}


JOINT = SessionAccount(uid="uid-joint", iban="DE01", name="Gemeinschaftskonto")


def test_reads_the_accounts_of_a_session() -> None:
    session = {
        "accounts": [
            {"uid": "uid-joint", "account_id": {"iban": "DE01"}, "name": "Gemeinschaftskonto"},
            {"uid": "uid-fix", "account_id": {"iban": "DE02"}, "name": None},
        ]
    }

    accounts = read_session_accounts(session)

    assert accounts == [JOINT, SessionAccount(uid="uid-fix", iban="DE02", name="")]


def test_fetches_every_account_from_the_history_start(tmp_path: Path) -> None:
    bank = FakeBank({"uid-joint": [{"transactions": []}], "uid-fix": [{"transactions": []}]})
    fixed_costs = SessionAccount(uid="uid-fix", iban="DE02", name="Fixkosten")

    fetch_all_accounts(bank, RawArchive(tmp_path), [JOINT, fixed_costs], HISTORY_START, NOW)

    assert bank.requested_starts == [HISTORY_START, HISTORY_START]


def test_archives_the_raw_pages_before_anything_else(tmp_path: Path) -> None:
    pages = [{"transactions": [raw_transaction("1", "2026-01-05")]}]
    bank = FakeBank({"uid-joint": pages})

    [summary] = fetch_all_accounts(bank, RawArchive(tmp_path), [JOINT], HISTORY_START, NOW)

    assert json.loads(summary.archive_file.read_text()) == pages
    balances_dir = tmp_path / "raw" / "balances" / "uid-joint"
    assert len(list(balances_dir.iterdir())) == 1


def test_summarizes_booked_and_pending_transactions_across_pages(tmp_path: Path) -> None:
    pages = [
        {"transactions": [raw_transaction("1", "2026-01-05"), raw_transaction("2", "2026-03-10")]},
        {"transactions": [raw_transaction("3", "2026-10-30", status="PDNG")]},
    ]
    bank = FakeBank({"uid-joint": pages})

    [summary] = fetch_all_accounts(bank, RawArchive(tmp_path), [JOINT], HISTORY_START, NOW)

    assert summary.booked_count == 2
    assert summary.pending_count == 1
    assert summary.first_booking == date(2026, 1, 5)
    assert summary.last_booking == date(2026, 10, 30)


def test_summary_of_an_account_without_transactions_has_no_dates(tmp_path: Path) -> None:
    bank = FakeBank({"uid-joint": [{"transactions": []}]})

    [summary] = fetch_all_accounts(bank, RawArchive(tmp_path), [JOINT], HISTORY_START, NOW)

    assert summary.booked_count == 0
    assert summary.first_booking is None


def test_keeps_the_archive_when_a_transaction_cannot_be_parsed(tmp_path: Path) -> None:
    broken = {"transaction_id": "x", "credit_debit_indicator": "????"}
    bank = FakeBank({"uid-joint": [{"transactions": [broken]}]})

    with pytest.raises(ValueError, match="credit_debit_indicator"):
        fetch_all_accounts(bank, RawArchive(tmp_path), [JOINT], HISTORY_START, NOW)

    assert list((tmp_path / "raw" / "transactions" / "uid-joint").iterdir())
