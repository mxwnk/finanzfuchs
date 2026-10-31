"""Turns the rows of the *Plan* and *Buchungen* tabs into the data the dashboard computes on.

The dashboard reads the sheet, not the local ledger: the sheet holds the assignments Max and
Merle changed by hand. All aggregation happens in the page so that every filter is instant.
"""

from datetime import date, datetime, timedelta
from typing import Any

from bauplan.sheets.transactions_tab import SPREADSHEET_EPOCH

YEARLY_RHYTHM = "Jahr"
MONTHS_PER_YEAR = 12

SheetRow = list[Any]


class DashboardDataError(ValueError):
    """A row of the sheet cannot be shown."""


def build_dataset(
    plan_rows: list[SheetRow], transaction_rows: list[SheetRow], generated_at: datetime
) -> dict[str, Any]:
    return {
        "generatedAt": generated_at.isoformat(),
        "plan": [
            _plan_line(row, row_number)
            for row_number, row in enumerate(plan_rows, 2)
            if _has_id(row)
        ],
        "transactions": [
            _transaction(row, row_number)
            for row_number, row in enumerate(transaction_rows, 2)
            if _has_id(row)
        ],
    }


def _plan_line(row: SheetRow, row_number: int) -> dict[str, Any]:
    cells = _pad(row, 9)
    try:
        amount = float(cells[4] or 0)
        return {
            "id": str(cells[0]),
            "type": str(cells[1]),
            "category": str(cells[2]),
            "description": str(cells[3]),
            "monthly": amount / MONTHS_PER_YEAR if cells[5] == YEARLY_RHYTHM else amount,
            "pot": str(cells[6]),
            "validFrom": _optional_date(cells[7]),
            "validUntil": _optional_date(cells[8]),
        }
    except (TypeError, ValueError) as error:
        raise DashboardDataError(f"Plan row {row_number} is unreadable: {error}") from error


def _transaction(row: SheetRow, row_number: int) -> dict[str, Any]:
    cells = _pad(row, 8)
    try:
        return {
            "id": str(cells[0]),
            "date": _from_sheet_date(cells[1]).isoformat(),
            "amount": float(cells[2]),
            "counterparty": str(cells[3]),
            "purpose": str(cells[4]),
            "line": str(cells[5]),
            "source": str(cells[6]),
            "note": str(cells[7]),
        }
    except (TypeError, ValueError) as error:
        raise DashboardDataError(f"Buchungen row {row_number} is unreadable: {error}") from error


def _has_id(row: SheetRow) -> bool:
    return bool(row) and str(row[0]).strip() != ""


def _pad(row: SheetRow, length: int) -> SheetRow:
    """The Sheets API leaves out empty cells at the end of a row."""
    return [*row, *[""] * (length - len(row))]


def _optional_date(value: Any) -> str | None:
    return _from_sheet_date(value).isoformat() if value not in ("", None) else None


def _from_sheet_date(value: Any) -> date:
    if not isinstance(value, int | float):
        raise ValueError(f"expected a date serial number, got {value!r}")
    return SPREADSHEET_EPOCH + timedelta(days=int(value))
