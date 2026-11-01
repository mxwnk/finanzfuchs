import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finanzfuchs.plan import FIXED, VARIABLE, PlanFileError, PlanLine, default_kind, load_plan
from finanzfuchs.storage.database import INITIAL_SCHEMA, Database
from finanzfuchs.storage.plan_store import PlanStore

HEADER = (
    "plan_line_id,type,category,description,amount,rhythm,"
    "monthly_amount,pot,valid_from,valid_until\n"
)


def test_reads_every_plan_line(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.csv"
    plan_file.write_text(
        HEADER
        + "gez,Ausgabe,Wohnen,GEZ,220.32,Jahr,18.36,Fixkosten,2026-01-01,\n"
        + "elterngeld,Einnahme,Einnahmen,Elterngeld,150,Monat,150.00,,2026-01-01,2026-12-31\n"
    )

    plan = load_plan(plan_file)

    assert plan == [
        PlanLine("gez", "Ausgabe", "Wohnen", "GEZ", Decimal("220.32"), "Jahr", "Fixkosten",
                 date(2026, 1, 1), None, FIXED),
        PlanLine("elterngeld", "Einnahme", "Einnahmen", "Elterngeld", Decimal("150"), "Monat", "",
                 date(2026, 1, 1), date(2026, 12, 31), FIXED),
    ]  # fmt: skip


def test_a_kind_column_wins_over_the_guess(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.csv"
    plan_file.write_text(
        HEADER.rstrip("\n") + ",kind\n"
        + "sportland,Ausgabe,Freizeit,Sportland,40,Monat,40,,2026-01-01,,fix\n"
    )  # fmt: skip

    [line] = load_plan(plan_file)

    assert line.kind == FIXED


def test_names_the_line_of_an_unreadable_amount(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.csv"
    plan_file.write_text(HEADER + "gez,Ausgabe,Wohnen,GEZ,viel,Jahr,,,2026-01-01,\n")

    with pytest.raises(PlanFileError, match="line 2"):
        load_plan(plan_file)


class TestDefaultKind:
    def test_income_arrives_at_a_known_amount(self) -> None:
        assert default_kind("Einnahme", "Einnahmen", "") == FIXED

    def test_standing_orders_to_a_pot_are_fixed(self) -> None:
        assert default_kind("Ausgabe", "Freizeit", "Funpark") == FIXED

    def test_housing_and_insurance_are_fixed(self) -> None:
        assert default_kind("Ausgabe", "Wohnen", "") == FIXED
        assert default_kind("Ausgabe", "Versicherungen", "") == FIXED

    def test_daily_needs_are_a_budget(self) -> None:
        assert default_kind("Ausgabe", "Täglicher Bedarf", "") == VARIABLE


class TestFixedCostsPot:
    def test_yearly_lines_and_reimbursed_lines_are_saved_up(self) -> None:
        yearly = PlanLine(
            "gez", "Ausgabe", "Wohnen", "GEZ", Decimal(220), "Jahr", "", date(2026, 1, 1), None
        )
        reimbursed = PlanLine("katzen", "Ausgabe", "Fixkosten", "Katzen", Decimal(150), "Monat",
                              "Fixkosten", date(2026, 1, 1), None)  # fmt: skip
        monthly = PlanLine(
            "sky", "Ausgabe", "Fixkosten", "Sky", Decimal(61), "Monat", "", date(2026, 1, 1), None
        )

        assert yearly.is_paid_from_fixed_costs_pot
        assert reimbursed.is_paid_from_fixed_costs_pot
        assert not monthly.is_paid_from_fixed_costs_pot


class TestMigration:
    def test_a_version_1_database_gets_kinds_guessed_for_its_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "old.sqlite3"
        _create_version_1_database(path)

        Database(path).initialize()

        with Database(path).connect() as connection:
            kinds = {line.plan_line_id: line.kind for line in PlanStore(connection).lines()}
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        assert kinds == {"lebensmittel": VARIABLE, "miete": FIXED}
        assert version == 2


def _create_version_1_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(INITIAL_SCHEMA)
    connection.executemany(
        "INSERT INTO plan_lines VALUES "
        "(?, ?, 'Ausgabe', ?, ?, 10000, 'Monat', '', '2026-01-01', NULL)",
        [("lebensmittel", 1, "Täglicher Bedarf", "Lebensmittel"), ("miete", 2, "Wohnen", "Miete")],
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()
