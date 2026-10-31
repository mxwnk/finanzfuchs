"""An Excel file with plan and transactions: a backup and a way to calculate on your own."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from finanzfuchs.dashboard.dataset import monthly_amount
from finanzfuchs.ledger import LedgerEntry
from finanzfuchs.plan import PlanLine

EURO_FORMAT = "#,##0.00 €"
DATE_FORMAT = "DD.MM.YYYY"
MAX_COLUMN_WIDTH = 50

TRANSACTION_HEADERS = ["Datum", "Betrag", "Gegenseite", "Verwendungszweck", "Planzeile",
                       "Kategorie", "Zuordnung", "Notiz", "ID"]  # fmt: skip
PLAN_HEADERS = ["ID", "Typ", "Kategorie", "Beschreibung", "Betrag", "Rhythmus", "Pro Monat",
                "Topf", "Gültig ab", "Gültig bis"]  # fmt: skip
SOURCE_LABELS = {"": "offen", "rule": "Regel", "manual": "von Hand"}


def build_workbook(plan: list[PlanLine], entries: list[LedgerEntry]) -> bytes:
    workbook = Workbook()
    transactions_sheet = workbook.active
    transactions_sheet.title = "Buchungen"
    _fill_transactions(transactions_sheet, entries, {line.plan_line_id: line for line in plan})
    _fill_plan(workbook.create_sheet("Plan"), plan)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _fill_transactions(
    sheet: Worksheet, entries: list[LedgerEntry], plan_by_id: dict[str, PlanLine]
) -> None:
    sheet.append(TRANSACTION_HEADERS)
    for entry in entries:
        transaction = entry.transaction
        line = plan_by_id.get(entry.plan_line_id or "")
        sheet.append([
            transaction.booking_date,
            float(transaction.amount),
            transaction.counterparty_name,
            transaction.purpose,
            line.description if line else "",
            line.category if line else "",
            SOURCE_LABELS[entry.source.value],
            entry.note,
            transaction.transaction_id,
        ])  # fmt: skip
    _format(sheet, euro_columns="B", date_columns="A")


def _fill_plan(sheet: Worksheet, plan: list[PlanLine]) -> None:
    sheet.append(PLAN_HEADERS)
    for line in plan:
        sheet.append([
            line.plan_line_id, line.line_type, line.category, line.description,
            float(line.amount), line.rhythm, monthly_amount(line), line.pot,
            line.valid_from, line.valid_until,
        ])  # fmt: skip
    _format(sheet, euro_columns="EG", date_columns="IJ")


def _format(sheet: Worksheet, euro_columns: str, date_columns: str) -> None:
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    for column in euro_columns:
        for cell in sheet[column][1:]:
            cell.number_format = EURO_FORMAT
    for column in date_columns:
        for cell in sheet[column][1:]:
            cell.number_format = DATE_FORMAT
    for column_cells in sheet.columns:
        longest = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(
            MAX_COLUMN_WIDTH, longest + 2
        )
