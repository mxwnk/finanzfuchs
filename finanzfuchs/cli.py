"""Command line: database (`import`, `seed`), web app (`serve`) and bank (`connect`, …)."""

import argparse
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from finanzfuchs.archive import RawArchive
from finanzfuchs.assignment.rules import RuleFileError
from finanzfuchs.banking.authorization import (
    AuthorizationRedirectError,
    choose_consent_end,
    read_authorization_code,
)
from finanzfuchs.banking.client import EnableBankingClient, EnableBankingError
from finanzfuchs.banking.transactions import TransactionParseError
from finanzfuchs.config import ConfigError, EnableBankingSettings, Settings
from finanzfuchs.importing import ImportSummary, import_dkb_export
from finanzfuchs.imports.dkb_csv import DkbExportError
from finanzfuchs.plan import PlanFileError
from finanzfuchs.seeding import SeedError, seed_from_files
from finanzfuchs.storage.database import Database, DatabaseError
from finanzfuchs.sync import (
    AccountSummary,
    SessionAccount,
    fetch_all_accounts,
    read_session_accounts,
)

BANK_COUNTRY = "DE"
CLI_USER = "Kommandozeile"
EXPECTED_ERRORS = (
    ConfigError,
    DatabaseError,
    DkbExportError,
    EnableBankingError,
    AuthorizationRedirectError,
    TransactionParseError,
    PlanFileError,
    RuleFileError,
    SeedError,
    OSError,
)

logger = logging.getLogger("finanzfuchs")


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
    """Add a DKB CSV export to the database; known rows are skipped, rules assign the rest."""
    export_file: Path = arguments.file
    with _database(settings).connect() as connection:
        summary = import_dkb_export(
            connection, export_file.read_text(encoding="utf-8-sig"), export_file.name, CLI_USER,
            datetime.now(UTC),
        )  # fmt: skip
    print(_format_import(summary))


def seed(settings: Settings, arguments: argparse.Namespace) -> None:
    """Take over plan, rules and DKB exports from the files used before the app."""
    source: Path = arguments.source
    exports = sorted((source / "imports").glob("*.csv"))
    with _database(settings).connect() as connection:
        summary = seed_from_files(
            connection, source / "plan.csv", source / "rules.csv", exports, datetime.now(UTC)
        )
    print(f"{summary.plan_line_count} plan lines and {summary.rule_count} rules taken over.")
    for result in summary.imports:
        print(_format_import(result))


def serve(settings: Settings, arguments: argparse.Namespace) -> None:
    from finanzfuchs.web.__main__ import main as run_web_app

    run_web_app()


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
    parser = argparse.ArgumentParser(prog="finanzfuchs", description=__doc__)
    commands = parser.add_subparsers(required=True)

    import_command = commands.add_parser("import", help="add a DKB CSV export to the database")
    import_command.add_argument("file", type=Path, help="the 'Umsatzliste' CSV from the DKB")
    import_command.set_defaults(command=import_export)

    seed_command = commands.add_parser("seed", help="take over plan, rules and exports once")
    seed_command.add_argument("source", type=Path, help="folder with plan.csv, rules.csv, imports/")
    seed_command.set_defaults(command=seed)

    commands.add_parser("serve", help="start the web app").set_defaults(command=serve)
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


def _database(settings: Settings) -> Database:
    database = Database(settings.database_path)
    database.initialize()
    return database


def _format_import(summary: ImportSummary) -> str:
    return (
        f"{summary.file_name}: {summary.added_count} added ({summary.assigned_count} by rule, "
        f"{summary.waiting_count} waiting), {summary.skipped_count} known, "
        f"{summary.pending_count} pending left out"
    )


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
    summaries = fetch_all_accounts(
        client, RawArchive(settings.data_dir), accounts, settings.history_start, datetime.now(UTC)
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
