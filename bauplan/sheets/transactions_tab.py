"""What the service may change on the *Buchungen* tab.

The sheet is the source of truth: the service appends transactions it has not written before and
fills a plan line only where the cell is still empty. Whatever Max or Merle chose stays.
"""

from dataclasses import dataclass
from datetime import date

from bauplan.assignment.rules import Assignment

TAB_TITLE = "Buchungen"
FIRST_DATA_ROW = 2
ID_COLUMN = 0
PLAN_LINE_COLUMN = 5
ASSIGNMENT_COLUMNS = "F:H"
"""Plan line, source and note: the cells a rule may fill."""
SPREADSHEET_EPOCH = date(1899, 12, 30)

SheetValue = str | int | float


@dataclass(frozen=True)
class CellFill:
    row_number: int
    values: list[SheetValue]


@dataclass(frozen=True)
class TransactionChanges:
    new_rows: list[list[SheetValue]]
    cell_fills: list[CellFill]


def to_sheet_date(day: date) -> int:
    """Dates go in as serial numbers, so bank text is never parsed by the sheet."""
    return (day - SPREADSHEET_EPOCH).days


def transaction_row(assignment: Assignment) -> list[SheetValue]:
    transaction = assignment.transaction
    return [
        transaction.transaction_id,
        to_sheet_date(transaction.booking_date),
        float(transaction.amount),
        transaction.counterparty_name,
        transaction.purpose,
        *_assignment_cells(assignment),
    ]


def plan_transaction_changes(
    existing_rows: list[list[SheetValue]], assignments: list[Assignment]
) -> TransactionChanges:
    row_numbers = _row_numbers_by_id(existing_rows)
    new_assignments = [a for a in assignments if a.transaction.transaction_id not in row_numbers]
    new_assignments.sort(key=lambda assignment: assignment.transaction.booking_date)
    return TransactionChanges(
        new_rows=[transaction_row(assignment) for assignment in new_assignments],
        cell_fills=_fills_for_open_rows(existing_rows, row_numbers, assignments),
    )


def _assignment_cells(assignment: Assignment) -> list[SheetValue]:
    if assignment.plan_line_id is None:
        return ["", "", ""]
    return [assignment.plan_line_id, f"Regel {assignment.rule_number}", assignment.note]


def _row_numbers_by_id(existing_rows: list[list[SheetValue]]) -> dict[str, int]:
    return {
        str(row[ID_COLUMN]): FIRST_DATA_ROW + index
        for index, row in enumerate(existing_rows)
        if row and row[ID_COLUMN]
    }


def _fills_for_open_rows(
    existing_rows: list[list[SheetValue]],
    row_numbers: dict[str, int],
    assignments: list[Assignment],
) -> list[CellFill]:
    fills = []
    for assignment in assignments:
        row_number = row_numbers.get(assignment.transaction.transaction_id)
        if row_number is None or assignment.plan_line_id is None:
            continue
        if _has_plan_line(existing_rows[row_number - FIRST_DATA_ROW]):
            continue
        fills.append(CellFill(row_number, _assignment_cells(assignment)))
    return sorted(fills, key=lambda fill: fill.row_number)


def _has_plan_line(row: list[SheetValue]) -> bool:
    return len(row) > PLAN_LINE_COLUMN and str(row[PLAN_LINE_COLUMN]).strip() != ""
