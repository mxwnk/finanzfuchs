from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bauplan.plan import PlanFileError, PlanLine, load_plan

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
                 date(2026, 1, 1), None),
        PlanLine("elterngeld", "Einnahme", "Einnahmen", "Elterngeld", Decimal("150"), "Monat", "",
                 date(2026, 1, 1), date(2026, 12, 31)),
    ]  # fmt: skip


def test_names_the_line_of_an_unreadable_amount(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.csv"
    plan_file.write_text(HEADER + "gez,Ausgabe,Wohnen,GEZ,viel,Jahr,,,2026-01-01,\n")

    with pytest.raises(PlanFileError, match="line 2"):
        load_plan(plan_file)
