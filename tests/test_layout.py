import re
from datetime import date
from decimal import Decimal

import pytest

from bauplan.plan import PlanLine
from bauplan.sheets.layout import (
    ANALYSIS_TAB,
    FIXED_COSTS_TAB,
    PLAN_LINES_TAB,
    PLAN_TAB,
    TAB_TITLES,
    TabWrite,
    add_tab_requests,
    format_requests,
    plan_rows,
    structure_writes,
)
from bauplan.sheets.transactions_tab import TAB_TITLE as TRANSACTIONS_TAB

TAB_IDS = {title: index for index, title in enumerate(TAB_TITLES)}


def all_formulas() -> list[str]:
    return [
        cell
        for write in structure_writes(2026)
        if write.as_formulas
        for row in write.rows
        for cell in row
        if isinstance(cell, str) and cell.startswith("=")
    ]


def write_for(cell_range_start: str) -> TabWrite:
    return next(w for w in structure_writes(2026) if w.cell_range.startswith(cell_range_start))


class TestTabs:
    def test_adds_only_the_missing_tabs(self) -> None:
        requests = add_tab_requests({PLAN_TAB, TRANSACTIONS_TAB, "Tabelle1"})

        added = [request["addSheet"]["properties"]["title"] for request in requests]
        assert added == [ANALYSIS_TAB, PLAN_LINES_TAB, FIXED_COSTS_TAB]

    def test_every_write_targets_a_bauplan_tab(self) -> None:
        for write in structure_writes(2026):
            tab = write.cell_range.split("!")[0].strip("'")
            assert tab in TAB_TITLES


class TestPlanRows:
    def test_writes_dates_as_serial_numbers_and_leaves_the_formula_column_free(self) -> None:
        line = PlanLine(
            "gez", "Ausgabe", "Wohnen", "GEZ", Decimal("220.32"), "Jahr", "Fixkosten",
            date(2026, 1, 1), None,
        )  # fmt: skip

        [row] = plan_rows([line])

        assert row == ["gez", "Ausgabe", "Wohnen", "GEZ", 220.32, "Jahr", "Fixkosten", 46023, ""]


class TestFormulas:
    def test_every_formula_has_balanced_parentheses_and_quotes(self) -> None:
        for formula in all_formulas():
            assert formula.count("(") == formula.count(")"), formula
            assert formula.count('"') % 2 == 0, formula

    def test_bank_data_is_never_written_as_formula(self) -> None:
        raw_writes = [w for w in structure_writes(2026) if not w.as_formulas]

        assert all(
            not str(cell).startswith("=") for w in raw_writes for row in w.rows for cell in row
        )

    def test_category_of_a_transaction_comes_from_its_plan_line(self) -> None:
        [[category, month]] = write_for(f"{TRANSACTIONS_TAB}!I1").rows

        assert "VLOOKUP(F2:F,Plan!A:C,3,FALSE)" in category
        assert "DATE(YEAR(B2:B),MONTH(B2:B),1)" in month

    def test_actual_per_category_sums_transactions_by_category_and_month(self) -> None:
        actual_block = write_for(f"{ANALYSIS_TAB}!A4").rows
        first_january_cell = actual_block[2][1]

        assert (
            "SUMIFS(Buchungen!$C:$C,Buchungen!$I:$I,$A6,Buchungen!$J:$J,B$5)" in first_january_cell
        )
        assert 'IF($A6="Einnahmen",1,-1)' in first_january_cell

    def test_planned_per_category_respects_validity(self) -> None:
        plan_block = write_for(f"{ANALYSIS_TAB}!A29").rows
        first_january_cell = plan_block[2][1]

        assert "Plan!$H$2:$H<=EOMONTH(B$30,0)" in first_january_cell
        assert '(Plan!$I$2:$I="")+(Plan!$I$2:$I>=B$30)' in first_january_cell

    def test_difference_subtracts_plan_from_actual_in_the_same_cell(self) -> None:
        difference_block = write_for(f"{ANALYSIS_TAB}!A54").rows

        assert difference_block[2][1] == '=IF($A56="","",B6-B31)'

    def test_planned_per_line_counts_every_month_not_only_the_first(self) -> None:
        # Without ARRAYFORMULA, LET keeps only the first month of SEQUENCE (seen in the live sheet).
        rows = write_for(f"{PLAN_LINES_TAB}!A5").rows

        assert "ARRAYFORMULA(LET(" in rows[0][4]
        assert "SEQUENCE(MONTH($B$2))" in rows[0][4]
        assert "ARRAYFORMULA(LET(" in rows[0][7]

    def test_plan_line_actual_counts_income_positive(self) -> None:
        rows = write_for(f"{PLAN_LINES_TAB}!A5").rows

        assert 'VLOOKUP($A5,Plan!$A:$B,2,FALSE)="Einnahme",1,-1' in rows[0][5]

    def test_fixed_costs_pot_splits_transfers_into_paid_in_and_refunded(self) -> None:
        january = write_for(f"'{FIXED_COSTS_TAB}'!A4").rows[0]

        assert january[2].startswith("=-SUMIFS(") and january[2].endswith(',"<0")')
        assert january[3].startswith("=SUMIFS(") and january[3].endswith(',">0")')
        assert 'Plan!$G$2:$G="Fixkosten"' in january[1]

    def test_formula_rows_cover_the_plan_and_categories(self) -> None:
        plan_lines = write_for(f"{PLAN_LINES_TAB}!A5")

        assert len(plan_lines.rows) == 150
        assert re.fullmatch(r"Planzeilen!A5:I154", plan_lines.cell_range)


class TestFormats:
    def test_the_plan_line_column_offers_the_plan_ids_as_dropdown(self) -> None:
        validations = [r for r in format_requests(TAB_IDS) if "setDataValidation" in r]

        [validation] = validations
        rule = validation["setDataValidation"]
        assert rule["range"]["sheetId"] == TAB_IDS[TRANSACTIONS_TAB]
        assert rule["rule"]["condition"]["values"] == [{"userEnteredValue": "=Plan!$A$2:$A"}]
        assert rule["rule"]["strict"] is False

    @pytest.mark.parametrize("title", TAB_TITLES)
    def test_freezes_the_header_of_every_tab(self, title: str) -> None:
        frozen = [
            r for r in format_requests(TAB_IDS)
            if r.get("updateSheetProperties", {}).get("properties", {}).get("sheetId")
            == TAB_IDS[title]
        ]  # fmt: skip

        assert len(frozen) == 1

    def test_plan_lines_freeze_down_to_their_header_row(self) -> None:
        frozen = next(
            r["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"]
            for r in format_requests(TAB_IDS)
            if r.get("updateSheetProperties", {}).get("properties", {}).get("sheetId")
            == TAB_IDS[PLAN_LINES_TAB]
        )

        assert frozen == 4
