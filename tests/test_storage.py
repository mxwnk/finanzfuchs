import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import plan_line

from finanzfuchs.assignment.rules import AssignmentRule
from finanzfuchs.banking.transactions import BankTransaction
from finanzfuchs.ledger import AssignmentSource
from finanzfuchs.storage.database import Database, DatabaseError
from finanzfuchs.storage.money import from_cents, to_cents
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.rule_store import RuleStore
from finanzfuchs.storage.session_store import PendingLogin, SessionStore, SessionUser
from finanzfuchs.storage.transaction_store import ImportRecord, TransactionStore

NOW = datetime(2026, 11, 1, 8, 0)


def bank_transaction(transaction_id: str, booking_date: date = date(2026, 3, 2)) -> BankTransaction:
    return BankTransaction(
        transaction_id=transaction_id,
        account_uid="DE01",
        booking_date=booking_date,
        amount=Decimal("-61.07"),
        counterparty_name="Sky",
        counterparty_iban="DE11",
        purpose="Abo",
        is_booked=True,
    )


def stored_import(connection: sqlite3.Connection) -> int:
    record = ImportRecord("export.csv", "DE01", NOW, "Max", 1, 0)
    return TransactionStore(connection).record_import(record)


class TestDatabase:
    def test_initializing_twice_keeps_the_data(self, database: Database) -> None:
        with database.connect() as connection:
            PlanStore(connection).add(plan_line("lebensmittel"))

        database.initialize()

        with database.connect() as connection:
            assert len(PlanStore(connection).list()) == 1

    def test_refuses_a_database_from_a_newer_version(self, tmp_path: Path) -> None:
        path = tmp_path / "newer.sqlite3"
        sqlite3.connect(path).execute("PRAGMA user_version = 99")

        with pytest.raises(DatabaseError, match="99"):
            Database(path).initialize()

    def test_rolls_back_when_the_block_fails(self, database: Database) -> None:
        with pytest.raises(RuntimeError), database.connect() as connection:
            PlanStore(connection).add(plan_line("lebensmittel"))
            raise RuntimeError("boom")

        with database.connect() as connection:
            assert PlanStore(connection).is_empty()


class TestMoney:
    def test_cents_round_trip_exactly(self) -> None:
        assert from_cents(to_cents(Decimal("-1409.84"))) == Decimal("-1409.84")

    def test_rounds_half_cents_up(self) -> None:
        assert to_cents(Decimal("18.365")) == 1837


class TestPlanStore:
    def test_keeps_the_order_the_plan_was_written_in(self, connection: sqlite3.Connection) -> None:
        store = PlanStore(connection)
        store.add(plan_line("wohnen"))
        store.add(plan_line("auto"))

        assert [line.plan_line_id for line in store.list()] == ["wohnen", "auto"]

    def test_updates_amount_and_validity(self, connection: sqlite3.Connection) -> None:
        store = PlanStore(connection)
        store.add(plan_line("lebensmittel"))
        changed = plan_line("lebensmittel", amount="900")
        changed = changed.__class__(**{**changed.__dict__, "valid_until": date(2026, 12, 31)})

        store.update(changed)

        assert store.get("lebensmittel") == changed


class TestRuleStore:
    def test_rules_added_at_the_top_are_tried_first(self, connection: sqlite3.Connection) -> None:
        PlanStore(connection).add(plan_line("lebensmittel"))
        store = RuleStore(connection)
        store.append(AssignmentRule("lebensmittel", counterparty_contains="general"))
        store.add_at_top(AssignmentRule("lebensmittel", counterparty_contains="specific"))

        order = [stored.rule.counterparty_contains for stored in store.list()]

        assert order == ["specific", "general"]

    def test_a_rule_needs_an_existing_plan_line(self, connection: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            RuleStore(connection).append(AssignmentRule("missing", counterparty_contains="x"))


class TestTransactionStore:
    def test_stores_transactions_exactly(self, connection: sqlite3.Connection) -> None:
        store = TransactionStore(connection)

        store.add([bank_transaction("t1")], stored_import(connection))

        [entry] = store.list()
        assert entry.transaction == bank_transaction("t1")
        assert entry.is_open

    def test_records_an_assignment_with_its_source(self, connection: sqlite3.Connection) -> None:
        PlanStore(connection).add(plan_line("sky-abo"))
        store = TransactionStore(connection)
        store.add([bank_transaction("t1")], stored_import(connection))

        store.assign("t1", "sky-abo", AssignmentSource.RULE, "ZWEIFEL: Abo?")

        entry = store.get("t1")
        assert entry is not None
        assert (entry.plan_line_id, entry.source) == ("sky-abo", AssignmentSource.RULE)
        assert entry.is_doubtful

    def test_lists_open_before_doubtful_and_newest_first(
        self, connection: sqlite3.Connection
    ) -> None:
        PlanStore(connection).add(plan_line("sky-abo"))
        store = TransactionStore(connection)
        store.add(
            [
                bank_transaction("doubt", date(2026, 5, 1)),
                bank_transaction("old-open", date(2026, 1, 1)),
                bank_transaction("new-open", date(2026, 4, 1)),
                bank_transaction("fine", date(2026, 6, 1)),
            ],
            stored_import(connection),
        )
        store.assign("doubt", "sky-abo", AssignmentSource.RULE, "ZWEIFEL: ?")
        store.assign("fine", "sky-abo", AssignmentSource.RULE, "")

        order = [entry.transaction.transaction_id for entry in store.needing_attention()]

        assert order == ["new-open", "old-open", "doubt"]

    def test_lists_the_latest_imports_first(self, connection: sqlite3.Connection) -> None:
        store = TransactionStore(connection)
        store.record_import(ImportRecord("old.csv", "DE01", NOW, "Max", 3, 0))
        store.record_import(ImportRecord("new.csv", "DE01", NOW, "Merle", 2, 1))

        assert [r.file_name for r in store.latest_imports(limit=5)] == ["new.csv", "old.csv"]


class TestSessionStore:
    def test_finds_the_user_of_a_valid_session(self, connection: sqlite3.Connection) -> None:
        store = SessionStore(connection)
        store.create_session("token", SessionUser("sub-1", "Merle"), NOW + timedelta(days=1))

        assert store.find_user("token", NOW) == SessionUser("sub-1", "Merle")

    def test_ignores_expired_and_unknown_sessions(self, connection: sqlite3.Connection) -> None:
        store = SessionStore(connection)
        store.create_session("token", SessionUser("sub-1", "Merle"), NOW - timedelta(seconds=1))

        assert store.find_user("token", NOW) is None
        assert store.find_user("other", NOW) is None

    def test_never_stores_the_token_itself(self, connection: sqlite3.Connection) -> None:
        SessionStore(connection).create_session(
            "secret-token", SessionUser("sub-1", "Merle"), NOW + timedelta(days=1)
        )

        stored = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
        assert "secret-token" not in stored

    def test_a_login_request_can_be_answered_only_once(
        self, connection: sqlite3.Connection
    ) -> None:
        store = SessionStore(connection)
        store.save_login("state", PendingLogin("nonce", "verifier"), NOW + timedelta(minutes=10))

        assert store.take_login("state", NOW) == PendingLogin("nonce", "verifier")
        assert store.take_login("state", NOW) is None

    def test_an_expired_login_request_is_refused(self, connection: sqlite3.Connection) -> None:
        store = SessionStore(connection)
        store.save_login("state", PendingLogin("nonce", "verifier"), NOW)

        assert store.take_login("state", NOW + timedelta(seconds=1)) is None
