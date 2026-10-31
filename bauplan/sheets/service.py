"""Setting up the Bauplan sheet and bringing new transactions into it."""

from dataclasses import dataclass
from typing import Any, Protocol

from bauplan.assignment.rules import Assignment
from bauplan.plan import PlanLine
from bauplan.sheets.layout import (
    DISPLAY_LOCALE,
    FORMULA_LOCALE,
    PLAN_TAB,
    add_tab_requests,
    format_requests,
    locale_request,
    plan_rows,
    structure_writes,
)
from bauplan.sheets.transactions_tab import (
    ASSIGNMENT_COLUMNS,
    FIRST_DATA_ROW,
    TAB_TITLE,
    plan_transaction_changes,
)

Rows = list[list[Any]]
PLAN_FIRST_ROW = 2
TRANSACTION_COLUMNS = "A:H"


class Sheets(Protocol):
    def tab_ids(self) -> dict[str, int]: ...

    def read_values(self, cell_range: str) -> Rows: ...

    def write_values(self, cell_range: str, rows: Rows, as_formulas: bool) -> None: ...

    def write_ranges(self, rows_by_range: dict[str, Rows]) -> None: ...

    def append_rows(self, cell_range: str, rows: Rows) -> None: ...

    def batch_update(self, requests: list[dict[str, Any]]) -> None: ...


@dataclass(frozen=True)
class SetupResult:
    added_tabs: list[str]
    plan_written: bool


@dataclass(frozen=True)
class SyncResult:
    appended_count: int
    filled_count: int
    open_count: int


def setup_sheet(sheets: Sheets, plan: list[PlanLine], year: int) -> SetupResult:
    """Safe to run again: it rewrites headers, formulas and formats, never the data."""
    added_tabs = _add_missing_tabs(sheets)
    sheets.batch_update([locale_request(FORMULA_LOCALE)])
    for write in structure_writes(year):
        sheets.write_values(write.cell_range, write.rows, write.as_formulas)
    plan_written = _write_plan_if_empty(sheets, plan)
    sheets.batch_update([*format_requests(sheets.tab_ids()), locale_request(DISPLAY_LOCALE)])
    return SetupResult(added_tabs=added_tabs, plan_written=plan_written)


def sync_transactions(sheets: Sheets, assignments: list[Assignment]) -> SyncResult:
    existing_rows = sheets.read_values(f"{TAB_TITLE}!A{FIRST_DATA_ROW}:H")
    changes = plan_transaction_changes(existing_rows, assignments)
    sheets.append_rows(f"{TAB_TITLE}!{TRANSACTION_COLUMNS}", changes.new_rows)
    sheets.write_ranges(
        {_assignment_range(fill.row_number): [fill.values] for fill in changes.cell_fills}
    )
    return SyncResult(
        appended_count=len(changes.new_rows),
        filled_count=len(changes.cell_fills),
        open_count=sum(1 for assignment in assignments if assignment.plan_line_id is None),
    )


def _add_missing_tabs(sheets: Sheets) -> list[str]:
    requests = add_tab_requests(set(sheets.tab_ids()))
    sheets.batch_update(requests)
    return [request["addSheet"]["properties"]["title"] for request in requests]


def _write_plan_if_empty(sheets: Sheets, plan: list[PlanLine]) -> bool:
    """Once the plan is in the sheet, Max and Merle own it there."""
    if sheets.read_values(f"{PLAN_TAB}!A{PLAN_FIRST_ROW}:A{PLAN_FIRST_ROW}"):
        return False
    last_row = PLAN_FIRST_ROW + len(plan) - 1
    sheets.write_values(
        f"{PLAN_TAB}!A{PLAN_FIRST_ROW}:I{last_row}", plan_rows(plan), as_formulas=False
    )
    return True


def _assignment_range(row_number: int) -> str:
    first_column, last_column = ASSIGNMENT_COLUMNS.split(":")
    return f"{TAB_TITLE}!{first_column}{row_number}:{last_column}{row_number}"
