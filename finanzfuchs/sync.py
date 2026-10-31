"""Fetches all accounts of the bank session and archives what the bank returned."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from finanzfuchs.archive import RawArchive
from finanzfuchs.banking.transactions import BankTransaction, parse_transaction

JsonObject = dict[str, Any]


class BankReader(Protocol):
    def fetch_transaction_pages(self, account_uid: str, date_from: date) -> list[JsonObject]: ...

    def fetch_balances(self, account_uid: str) -> JsonObject: ...


@dataclass(frozen=True)
class SessionAccount:
    uid: str
    iban: str
    name: str


@dataclass(frozen=True)
class AccountSummary:
    account: SessionAccount
    booked_count: int
    pending_count: int
    first_booking: date | None
    last_booking: date | None
    archive_file: Path


def read_session_accounts(session: JsonObject) -> list[SessionAccount]:
    return [_read_session_account(raw_account) for raw_account in session.get("accounts", [])]


def fetch_all_accounts(
    bank: BankReader,
    archive: RawArchive,
    accounts: list[SessionAccount],
    date_from: date,
    now: datetime,
) -> list[AccountSummary]:
    return [_fetch_account(bank, archive, account, date_from, now) for account in accounts]


def _read_session_account(raw_account: JsonObject) -> SessionAccount:
    account_id = raw_account.get("account_id") or {}
    return SessionAccount(
        uid=raw_account["uid"],
        iban=account_id.get("iban") or "",
        name=raw_account.get("name") or "",
    )


def _fetch_account(
    bank: BankReader,
    archive: RawArchive,
    account: SessionAccount,
    date_from: date,
    now: datetime,
) -> AccountSummary:
    pages = bank.fetch_transaction_pages(account.uid, date_from)
    # Archived before parsing: a parse error must never cost the only copy of old transactions.
    archive_file = archive.save_transaction_pages(account.uid, pages, now)
    archive.save_balances(account.uid, bank.fetch_balances(account.uid), now)
    transactions = _parse_pages(pages, account.uid)
    return _summarize(account, transactions, archive_file)


def _parse_pages(pages: list[JsonObject], account_uid: str) -> list[BankTransaction]:
    return [
        parse_transaction(raw_transaction, account_uid)
        for page in pages
        for raw_transaction in page.get("transactions", [])
    ]


def _summarize(
    account: SessionAccount, transactions: list[BankTransaction], archive_file: Path
) -> AccountSummary:
    booking_dates = [transaction.booking_date for transaction in transactions]
    booked_count = sum(1 for transaction in transactions if transaction.is_booked)
    return AccountSummary(
        account=account,
        booked_count=booked_count,
        pending_count=len(transactions) - booked_count,
        first_booking=min(booking_dates, default=None),
        last_booking=max(booking_dates, default=None),
        archive_file=archive_file,
    )
