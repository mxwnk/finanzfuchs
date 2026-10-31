from datetime import date
from decimal import Decimal
from typing import Any

from bauplan.assignment.rules import Assignment
from bauplan.banking.transactions import BankTransaction
from bauplan.plan import PlanLine
from bauplan.sheets.layout import PLAN_TAB, TAB_TITLES
from bauplan.sheets.service import setup_sheet, sync_transactions

GEZ = PlanLine(
    "gez",
    "Ausgabe",
    "Wohnen",
    "GEZ",
    Decimal("220.32"),
    "Jahr",
    "Fixkosten",
    date(2026, 1, 1),
    None,
)


class FakeSheets:
    """Keeps values per range as written; enough to observe what the service does."""

    def __init__(self, tabs: dict[str, int], values: dict[str, list[list[Any]]] | None = None):
        self.tabs = dict(tabs)
        self.values = values or {}
        self.writes: list[tuple[str, bool]] = []
        self.appended: list[list[Any]] = []
        self.range_writes: dict[str, list[list[Any]]] = {}
        self.structural_requests: list[dict[str, Any]] = []
        self.locale = "de_DE"
        self.formula_write_locales: list[str] = []

    def tab_ids(self) -> dict[str, int]:
        return dict(self.tabs)

    def read_values(self, cell_range: str) -> list[list[Any]]:
        return self.values.get(cell_range, [])

    def write_values(self, cell_range: str, rows: list[list[Any]], as_formulas: bool) -> None:
        self.writes.append((cell_range, as_formulas))
        if as_formulas:
            self.formula_write_locales.append(self.locale)

    def write_ranges(self, rows_by_range: dict[str, list[list[Any]]]) -> None:
        self.range_writes.update(rows_by_range)

    def append_rows(self, cell_range: str, rows: list[list[Any]]) -> None:
        self.appended.extend(rows)

    def batch_update(self, requests: list[dict[str, Any]]) -> None:
        self.structural_requests.extend(requests)
        for request in requests:
            if "updateSpreadsheetProperties" in request:
                self.locale = request["updateSpreadsheetProperties"]["properties"]["locale"]
            if "addSheet" in request:
                title = request["addSheet"]["properties"]["title"]
                self.tabs[title] = len(self.tabs) + 100


def assignment(transaction_id: str, plan_line_id: str | None = "gez") -> Assignment:
    transaction = BankTransaction(
        transaction_id=transaction_id,
        account_uid="DE01",
        booking_date=date(2026, 1, 5),
        amount=Decimal("-220.32"),
        counterparty_name="Rundfunk",
        counterparty_iban="DE28",
        purpose="Beitrag",
        is_booked=True,
    )
    return Assignment(transaction, plan_line_id, 3 if plan_line_id else None, "")


class TestSetup:
    def test_adds_the_missing_tabs_before_formatting_them(self) -> None:
        sheets = FakeSheets({"Tabelle1": 0})

        result = setup_sheet(sheets, [GEZ], year=2026)

        assert set(result.added_tabs) == set(TAB_TITLES)
        assert set(TAB_TITLES) <= set(sheets.tabs)

    def test_writes_formulas_in_us_syntax_and_leaves_the_sheet_german(self) -> None:
        sheets = FakeSheets({title: index for index, title in enumerate(TAB_TITLES)})

        setup_sheet(sheets, [GEZ], year=2026)

        assert set(sheets.formula_write_locales) == {"en_US"}
        assert sheets.locale == "de_DE"

    def test_writes_the_plan_into_an_empty_plan_tab(self) -> None:
        sheets = FakeSheets({title: index for index, title in enumerate(TAB_TITLES)})

        result = setup_sheet(sheets, [GEZ], year=2026)

        assert result.plan_written
        assert (f"{PLAN_TAB}!A2:I2", False) in sheets.writes

    def test_keeps_a_plan_that_is_already_in_the_sheet(self) -> None:
        sheets = FakeSheets(
            {title: index for index, title in enumerate(TAB_TITLES)},
            values={f"{PLAN_TAB}!A2:A2": [["gez"]]},
        )

        result = setup_sheet(sheets, [GEZ], year=2026)

        assert not result.plan_written
        assert all(not cell_range.startswith(f"{PLAN_TAB}!A2") for cell_range, _ in sheets.writes)


class TestSync:
    def test_appends_new_transactions_and_fills_open_plan_lines(self) -> None:
        existing = [["t1", 46027, -220.32, "Rundfunk", "Beitrag"]]
        sheets = FakeSheets({}, values={"Buchungen!A2:H": existing})

        result = sync_transactions(sheets, [assignment("t1"), assignment("t2")])

        assert [row[0] for row in sheets.appended] == ["t2"]
        assert sheets.range_writes == {"Buchungen!F2:H2": [["gez", "Regel 3", ""]]}
        assert result.appended_count == 1
        assert result.filled_count == 1

    def test_counts_transactions_still_waiting_for_a_plan_line(self) -> None:
        sheets = FakeSheets({})

        result = sync_transactions(sheets, [assignment("t1", plan_line_id=None)])

        assert result.open_count == 1
