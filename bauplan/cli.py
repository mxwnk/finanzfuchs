"""Command line for imports, the Google Sheet, the dashboard and the bank connection."""

import argparse
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from bauplan.archive import RawArchive
from bauplan.assignment.rules import RuleFileError, assign, load_rules
from bauplan.banking.authorization import (
    AuthorizationRedirectError,
    choose_consent_end,
    read_authorization_code,
)
from bauplan.banking.client import EnableBankingClient, EnableBankingError
from bauplan.banking.transactions import TransactionParseError
from bauplan.config import ConfigError, EnableBankingSettings, Settings, SheetSettings
from bauplan.dashboard.dataset import DashboardDataError, build_dataset
from bauplan.dashboard.render import render_dashboard
from bauplan.imports.dkb_csv import DkbExportError, parse_dkb_export
from bauplan.ledger import TransactionLedger
from bauplan.plan import PlanFileError, load_plan
from bauplan.sheets.client import SheetsClient, SheetsError
from bauplan.sheets.google_auth import GoogleAuthError, ServiceAccount, ServiceAccountTokens
from bauplan.sheets.service import setup_sheet, sync_transactions
from bauplan.sync import AccountSummary, SessionAccount, fetch_all_accounts, read_session_accounts

BANK_COUNTRY = "DE"
REQUEST_TIMEOUT_SECONDS = 30.0
LEDGER_FILE_NAME = "transactions.csv"
PLAN_FILE_NAME = "plan.csv"
RULES_FILE_NAME = "rules.csv"
DASHBOARD_FILE_NAME = "dashboard.html"
EXPECTED_ERRORS = (
    ConfigError,
    DkbExportError,
    EnableBankingError,
    AuthorizationRedirectError,
    TransactionParseError,
    PlanFileError,
    RuleFileError,
    GoogleAuthError,
    SheetsError,
    DashboardDataError,
    OSError,
)

logger = logging.getLogger("bauplan")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Every request at INFO would bury the result lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    arguments = _build_parser().parse_args(argv)
    try:
        settings = Settings.from_environment(os.environ)
        arguments.command(settings, arguments)
    except EXPECTED_ERRORS as error:
        logger.error("%s", error)
        return 1
    return 0


def import_export(settings: Settings, arguments: argparse.Namespace) -> None:
    """Add a DKB CSV export to the ledger; rows already in it are skipped."""
    export_file: Path = arguments.file
    export = parse_dkb_export(export_file.read_text(encoding="utf-8-sig"))
    result = _ledger(settings).add(export.transactions)
    print(
        f"{export_file.name} ({export.account_iban}): {result.added_count} added, "
        f"{result.skipped_count} already known, {result.pending_count} pending left out"
    )


def set_up_sheet(settings: Settings, arguments: argparse.Namespace) -> None:
    """Create the tabs, formulas and formats; the plan goes in only while the tab is empty."""
    plan = load_plan(settings.data_dir / PLAN_FILE_NAME)
    result = setup_sheet(_sheets_client(), plan, settings.history_start.year)
    added = ", ".join(result.added_tabs) or "none"
    plan_state = f"{len(plan)} plan lines written" if result.plan_written else "plan kept"
    print(f"Sheet ready. Tabs added: {added}; {plan_state}.")


def sync_sheet(settings: Settings, arguments: argparse.Namespace) -> None:
    """Append new transactions and fill plan lines that are still empty in the sheet."""
    transactions = _ledger(settings).load()
    rules = load_rules(settings.data_dir / RULES_FILE_NAME)
    result = sync_transactions(_sheets_client(), assign(transactions, rules))
    print(
        f"{result.appended_count} transactions appended, {result.filled_count} plan lines "
        f"filled, {result.open_count} without a matching rule"
    )


def build_dashboard(settings: Settings, arguments: argparse.Namespace) -> None:
    """Render the sheet's plan and transactions into a local HTML dashboard."""
    sheets = _sheets_client()
    dataset = build_dataset(
        sheets.read_values("Plan!A2:I"), sheets.read_values("Buchungen!A2:H"), datetime.now()
    )
    target = settings.data_dir / DASHBOARD_FILE_NAME
    target.write_text(render_dashboard(dataset), encoding="utf-8")
    print(f"Dashboard with {len(dataset['transactions'])} transactions written to {target}")


def connect(settings: Settings, arguments: argparse.Namespace) -> None:
    """Approve the access in the DKB app, then back up the full history right away."""
    bank_settings = EnableBankingSettings.from_environment(os.environ)
    client = _create_client(bank_settings)
    now = datetime.now(UTC)
    bank = client.find_bank(bank_settings.bank_name, BANK_COUNTRY)
    consent_end = choose_consent_end(now, bank.get("maximum_consent_validity"))
    state = str(uuid.uuid4())
    approval_url = client.start_authorization(bank, consent_end, state, bank_settings.redirect_url)

    redirect_url = _ask_for_redirect(approval_url, consent_end)
    session = client.create_session(read_authorization_code(redirect_url, state))
    RawArchive(settings.data_dir).save_session(session)
    print(f"Session {session['session_id']} saved; access valid until {consent_end:%Y-%m-%d}.")

    # Banks often hand out the full history only shortly after the approval.
    _fetch_and_report(client, settings, session)


def show_accounts(settings: Settings, arguments: argparse.Namespace) -> None:
    client = _create_client(EnableBankingSettings.from_environment(os.environ))
    saved_session = RawArchive(settings.data_dir).load_session()
    session_status = client.fetch_session(saved_session["session_id"])
    access = session_status.get("access", {})
    print(
        f"Session status: {session_status.get('status')}, valid until {access.get('valid_until')}"
    )
    for account in read_session_accounts(saved_session):
        print(_format_account(account))


def fetch(settings: Settings, arguments: argparse.Namespace) -> None:
    client = _create_client(EnableBankingSettings.from_environment(os.environ))
    session = RawArchive(settings.data_dir).load_session()
    _fetch_and_report(client, settings, session)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bauplan", description=__doc__)
    commands = parser.add_subparsers(required=True)

    import_command = commands.add_parser("import", help="add a DKB CSV export to the ledger")
    import_command.add_argument("file", type=Path, help="the 'Umsatzliste' CSV from the DKB")
    import_command.set_defaults(command=import_export)

    commands.add_parser(
        "sheet-setup", help="create tabs, formulas and formats in the Google Sheet"
    ).set_defaults(command=set_up_sheet)
    commands.add_parser(
        "sheet-sync", help="bring new transactions and assignments into the Google Sheet"
    ).set_defaults(command=sync_sheet)
    commands.add_parser(
        "dashboard", help="write the local HTML dashboard from the Google Sheet"
    ).set_defaults(command=build_dashboard)
    commands.add_parser(
        "connect", help="approve the bank access and back up the history"
    ).set_defaults(command=connect)
    commands.add_parser("accounts", help="show the accounts of the bank session").set_defaults(
        command=show_accounts
    )
    commands.add_parser("fetch", help="fetch and archive all transactions").set_defaults(
        command=fetch
    )
    return parser


def _ledger(settings: Settings) -> TransactionLedger:
    return TransactionLedger(settings.data_dir / LEDGER_FILE_NAME)


def _sheets_client() -> SheetsClient:
    sheet_settings = SheetSettings.from_environment(os.environ)
    account = ServiceAccount.from_key_file(sheet_settings.service_account_file)
    tokens = ServiceAccountTokens(account, httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS))
    return SheetsClient.connect(sheet_settings.spreadsheet_id, tokens)


def _create_client(bank_settings: EnableBankingSettings) -> EnableBankingClient:
    return EnableBankingClient.connect(
        bank_settings.application_id, bank_settings.read_private_key()
    )


def _ask_for_redirect(approval_url: str, consent_end: datetime) -> str:
    print("1. Open this address and approve the access in the DKB app:")
    print(f"   {approval_url}")
    print(f"   (access will be valid until {consent_end:%Y-%m-%d})")
    print("2. The browser then opens the redirect address; it may show an error page.")
    return input("3. Paste the full address from the browser's address bar: ")


def _fetch_and_report(client: EnableBankingClient, settings: Settings, session: dict) -> None:
    accounts = read_session_accounts(session)
    now = datetime.now(UTC)
    summaries = fetch_all_accounts(
        client, RawArchive(settings.data_dir), accounts, settings.history_start, now
    )
    for summary in summaries:
        print(_format_summary(summary))


def _format_account(account: SessionAccount) -> str:
    return f"{account.iban:<24} {account.name:<30} uid {account.uid}"


def _format_summary(summary: AccountSummary) -> str:
    period = f"{summary.first_booking} to {summary.last_booking}" if summary.first_booking else "-"
    return (
        f"{_format_account(summary.account)}\n"
        f"    {summary.booked_count} booked, {summary.pending_count} pending, {period}\n"
        f"    archived in {summary.archive_file}"
    )


if __name__ == "__main__":
    sys.exit(main())
