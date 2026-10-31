import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from conftest import dkb_export, export_row, plan_line

from finanzfuchs.assignment.rules import AssignmentRule
from finanzfuchs.assignment.service import AssignmentError, assign_by_hand, confirm
from finanzfuchs.importing import import_dkb_export
from finanzfuchs.ledger import AssignmentSource
from finanzfuchs.seeding import SeedError, seed_from_files
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.rule_store import RuleStore
from finanzfuchs.storage.transaction_store import TransactionStore

NOW = datetime(2026, 11, 1, 8, 0)
REWE = export_row("30.10.26", "REWE", "-20,30")
IKEA = export_row("29.10.26", "IKEA", "-87,94")
PENDING = export_row("31.10.26", "Lidl", "-5,00", status="Vorgemerkt")


def import_text(connection: sqlite3.Connection, *rows: str):
    return import_dkb_export(connection, dkb_export(*rows), "export.csv", "Merle", NOW)


def with_plan_and_rule(connection: sqlite3.Connection) -> None:
    PlanStore(connection).add(plan_line("lebensmittel"))
    PlanStore(connection).add(plan_line("anschaffungen", category="Ungeplant", amount="0"))
    RuleStore(connection).append(AssignmentRule("lebensmittel", counterparty_contains="REWE"))


def entry(connection: sqlite3.Connection, payee: str):
    return next(
        e
        for e in TransactionStore(connection).entries()
        if e.transaction.counterparty_name == payee
    )


class TestImport:
    def test_adds_booked_transactions_and_leaves_out_pending_ones(
        self, connection: sqlite3.Connection
    ) -> None:
        summary = import_text(connection, REWE, IKEA, PENDING)

        assert (summary.added_count, summary.pending_count) == (2, 1)
        assert len(TransactionStore(connection).entries()) == 2

    def test_a_second_import_of_the_same_rows_adds_nothing(
        self, connection: sqlite3.Connection
    ) -> None:
        import_text(connection, REWE)

        summary = import_text(connection, REWE, IKEA)

        assert (summary.added_count, summary.skipped_count) == (1, 1)

    def test_assigns_new_transactions_by_the_rules(self, connection: sqlite3.Connection) -> None:
        with_plan_and_rule(connection)

        summary = import_text(connection, REWE, IKEA)

        assert (summary.assigned_count, summary.waiting_count) == (1, 1)
        assert entry(connection, "REWE").plan_line_id == "lebensmittel"
        assert entry(connection, "REWE").source == AssignmentSource.RULE

    def test_remembers_who_imported_which_file(self, connection: sqlite3.Connection) -> None:
        import_text(connection, REWE)

        [record] = TransactionStore(connection).latest_imports(limit=1)

        assert (record.file_name, record.imported_by, record.added_count) == (
            "export.csv",
            "Merle",
            1,
        )


class TestAssignByHand:
    def test_marks_the_choice_as_manual(self, connection: sqlite3.Connection) -> None:
        with_plan_and_rule(connection)
        import_text(connection, IKEA)
        ikea = entry(connection, "IKEA")

        assign_by_hand(connection, ikea.transaction.transaction_id, "anschaffungen", remember=False)

        assigned = entry(connection, "IKEA")
        assert (assigned.plan_line_id, assigned.source) == (
            "anschaffungen",
            AssignmentSource.MANUAL,
        )

    def test_remembering_assigns_the_other_waiting_ones_of_that_counterparty(
        self, connection: sqlite3.Connection
    ) -> None:
        with_plan_and_rule(connection)
        import_text(connection, IKEA, export_row("01.10.26", "IKEA", "-12,00"))
        first = entry(connection, "IKEA")

        result = assign_by_hand(
            connection, first.transaction.transaction_id, "anschaffungen", remember=True
        )

        assert result == result.__class__(rule_created=True, also_assigned=1)
        assert all(e.plan_line_id == "anschaffungen" for e in TransactionStore(connection).entries()
                   if e.transaction.counterparty_name == "IKEA")  # fmt: skip

    def test_a_remembered_rule_never_overrides_a_manual_choice(
        self, connection: sqlite3.Connection
    ) -> None:
        with_plan_and_rule(connection)
        import_text(connection, REWE, export_row("01.10.26", "REWE", "-3,00"))
        first, second = [e for e in TransactionStore(connection).entries()]
        assign_by_hand(
            connection, first.transaction.transaction_id, "anschaffungen", remember=False
        )

        assign_by_hand(connection, second.transaction.transaction_id, "lebensmittel", remember=True)

        assert (
            TransactionStore(connection).get(first.transaction.transaction_id).plan_line_id
            == "anschaffungen"
        )

    def test_rejects_an_unknown_plan_line(self, connection: sqlite3.Connection) -> None:
        import_text(connection, IKEA)

        with pytest.raises(AssignmentError, match="plan line"):
            assign_by_hand(
                connection, entry(connection, "IKEA").transaction.transaction_id, "x", False
            )

    def test_rejects_an_unknown_transaction(self, connection: sqlite3.Connection) -> None:
        with_plan_and_rule(connection)

        with pytest.raises(AssignmentError, match="transaction"):
            assign_by_hand(connection, "missing", "lebensmittel", remember=False)


class TestConfirm:
    def test_confirming_a_doubt_keeps_the_line_and_clears_the_doubt(
        self, connection: sqlite3.Connection
    ) -> None:
        PlanStore(connection).add(plan_line("lebensmittel"))
        RuleStore(connection).append(
            AssignmentRule("lebensmittel", counterparty_contains="REWE", note="ZWEIFEL: wirklich?")
        )
        import_text(connection, REWE)
        rewe = entry(connection, "REWE")
        assert rewe.is_doubtful

        confirm(connection, rewe.transaction.transaction_id)

        confirmed = entry(connection, "REWE")
        assert (confirmed.plan_line_id, confirmed.source, confirmed.note) == (
            "lebensmittel", AssignmentSource.MANUAL, "")  # fmt: skip
        assert not confirmed.needs_attention

    def test_an_open_transaction_cannot_be_confirmed(self, connection: sqlite3.Connection) -> None:
        import_text(connection, IKEA)

        with pytest.raises(AssignmentError, match="no plan line"):
            confirm(connection, entry(connection, "IKEA").transaction.transaction_id)


class TestSeed:
    @pytest.fixture
    def files(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        plan = tmp_path / "plan.csv"
        plan.write_text(
            "plan_line_id,type,category,description,amount,rhythm,monthly_amount,pot,valid_from,valid_until\n"
            "lebensmittel,Ausgabe,Täglicher Bedarf,Lebensmittel,800,Monat,800.00,,2026-01-01,\n"
        )
        rules = tmp_path / "rules.csv"
        rules.write_text(
            "plan_line_id,counterparty_contains,purpose_contains,counterparty_iban,direction,note\n"
            "lebensmittel,REWE,,,,\n"
        )
        export = tmp_path / "export.csv"
        export.write_text(dkb_export(REWE, IKEA), encoding="utf-8")
        return plan, rules, export

    def test_takes_over_plan_rules_and_exports(
        self, connection: sqlite3.Connection, files: tuple[Path, Path, Path]
    ) -> None:
        plan, rules, export = files

        summary = seed_from_files(connection, plan, rules, [export], NOW)

        assert (summary.plan_line_count, summary.rule_count) == (1, 1)
        assert summary.imports[0].assigned_count == 1

    def test_refuses_to_seed_a_database_that_has_a_plan(
        self, connection: sqlite3.Connection, files: tuple[Path, Path, Path]
    ) -> None:
        plan, rules, export = files
        seed_from_files(connection, plan, rules, [export], NOW)

        with pytest.raises(SeedError, match="already"):
            seed_from_files(connection, plan, rules, [export], NOW)
