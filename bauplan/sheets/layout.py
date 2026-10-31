"""The structure of the Bauplan sheet: tabs, headers, formulas and formats.

Formulas use the en_US syntax (English names, commas). The API parses them in the spreadsheet's
locale, so they are written while the sheet is switched to `FORMULA_LOCALE`; Google stores them
independent of locale and shows them in German afterwards. Every analysis is a formula, so
assigning a transaction by hand in the sheet updates all views at once.
"""

from dataclasses import dataclass
from typing import Any

from bauplan.plan import PlanLine
from bauplan.sheets.transactions_tab import TAB_TITLE as TRANSACTIONS_TAB
from bauplan.sheets.transactions_tab import SheetValue, to_sheet_date

PLAN_TAB = "Plan"
ANALYSIS_TAB = "Auswertung"
PLAN_LINES_TAB = "Planzeilen"
FIXED_COSTS_TAB = "Fixkosten-Topf"
TAB_TITLES = (ANALYSIS_TAB, PLAN_LINES_TAB, FIXED_COSTS_TAB, TRANSACTIONS_TAB, PLAN_TAB)

FORMULA_LOCALE = "en_US"
DISPLAY_LOCALE = "de_DE"
"""German number display: `1.234,56 €`."""

INCOME_CATEGORY = "Einnahmen"
INCOME_TYPE = "Einnahme"
FIXED_COSTS_POT = "Fixkosten"
FIXED_COSTS_TRANSFER_LINE = "umbuchung"

MONTHS = range(1, 13)
MONTH_COLUMNS = "BCDEFGHIJKLM"
CATEGORY_ROWS = 20
PLAN_LINE_ROWS = 150
ANALYSIS_BLOCK_STARTS = {"Ist": 4, "Plan": 29, "Ist − Plan": 54}
"""Each block: title row, month header row, then one row per category."""
PLAN_LINES_FIRST_ROW = 5
FIXED_COSTS_FIRST_ROW = 4

EURO_FORMAT = {"type": "NUMBER", "pattern": "#,##0.00 €;-#,##0.00 €"}
DATE_FORMAT = {"type": "DATE", "pattern": "dd.mm.yyyy"}
MONTH_FORMAT = {"type": "DATE", "pattern": "mmm yyyy"}

PLAN_HEADERS = [
    "ID", "Typ", "Kategorie", "Beschreibung", "Betrag", "Rhythmus", "Topf", "Gültig ab",
    "Gültig bis",
]  # fmt: skip
TRANSACTION_HEADERS = [
    "ID", "Datum", "Betrag", "Gegenseite", "Verwendungszweck", "Planzeile", "Quelle", "Notiz",
]  # fmt: skip


@dataclass(frozen=True)
class TabWrite:
    cell_range: str
    rows: list[list[SheetValue]]
    as_formulas: bool


def add_tab_requests(existing_titles: set[str]) -> list[dict[str, Any]]:
    return [
        {"addSheet": {"properties": {"title": title, "index": index}}}
        for index, title in enumerate(TAB_TITLES)
        if title not in existing_titles
    ]


def locale_request(locale: str) -> dict[str, Any]:
    return {"updateSpreadsheetProperties": {"properties": {"locale": locale}, "fields": "locale"}}


def plan_rows(plan: list[PlanLine]) -> list[list[SheetValue]]:
    """Columns A–I; column J ("Pro Monat") is a formula over the whole column."""
    return [_plan_row(line) for line in plan]


def structure_writes(year: int) -> list[TabWrite]:
    return [
        *_plan_tab_writes(),
        *_transactions_tab_writes(),
        *_analysis_tab_writes(year),
        *_plan_lines_tab_writes(),
        *_fixed_costs_tab_writes(),
    ]


def format_requests(tab_ids: dict[str, int]) -> list[dict[str, Any]]:
    plan, transactions = tab_ids[PLAN_TAB], tab_ids[TRANSACTIONS_TAB]
    analysis, plan_lines = tab_ids[ANALYSIS_TAB], tab_ids[PLAN_LINES_TAB]
    fixed_costs = tab_ids[FIXED_COSTS_TAB]
    return [
        *_header_requests(plan, header_row=1),
        _number_format(plan, "E", EURO_FORMAT),
        _number_format(plan, "J", EURO_FORMAT),
        _number_format(plan, "H", DATE_FORMAT),
        _number_format(plan, "I", DATE_FORMAT),
        *_header_requests(transactions, header_row=1),
        _number_format(transactions, "B", DATE_FORMAT),
        _number_format(transactions, "C", EURO_FORMAT),
        _number_format(transactions, "J", MONTH_FORMAT),
        _plan_line_dropdown(transactions),
        *_header_requests(analysis, header_row=0),
        _cell_box_format(analysis, "B2:B2", MONTH_FORMAT),
        *_analysis_formats(analysis),
        *_header_requests(plan_lines, header_row=PLAN_LINES_FIRST_ROW - 2),
        _cell_box_format(plan_lines, "B2:B2", MONTH_FORMAT),
        *[_number_format(plan_lines, column, EURO_FORMAT) for column in "EFGH"],
        *_header_requests(fixed_costs, header_row=FIXED_COSTS_FIRST_ROW - 2),
        _number_format(fixed_costs, "A", MONTH_FORMAT, first_row=FIXED_COSTS_FIRST_ROW - 1),
        *[_number_format(fixed_costs, column, EURO_FORMAT) for column in "BCDEF"],
    ]


# --- Plan -----------------------------------------------------------------------------------


def _plan_row(line: PlanLine) -> list[SheetValue]:
    return [
        line.plan_line_id,
        line.line_type,
        line.category,
        line.description,
        float(line.amount),
        line.rhythm,
        line.pot,
        to_sheet_date(line.valid_from),
        to_sheet_date(line.valid_until) if line.valid_until else "",
    ]


def _plan_tab_writes() -> list[TabWrite]:
    monthly = '={"Pro Monat";ARRAYFORMULA(IF(A2:A="",,IF(F2:F="Jahr",E2:E/12,E2:E)))}'
    return [
        TabWrite(f"{PLAN_TAB}!A1:I1", [PLAN_HEADERS], as_formulas=False),
        TabWrite(f"{PLAN_TAB}!J1", [[monthly]], as_formulas=True),
    ]


def _plan_monthly_sum(conditions: str, month_cell: str) -> str:
    """Sum of "Pro Monat" over the plan lines that match and are valid in that month."""
    return (
        f"SUM(IFERROR(FILTER({PLAN_TAB}!$J$2:$J,{conditions},"
        f"{PLAN_TAB}!$H$2:$H<=EOMONTH({month_cell},0),"
        f'({PLAN_TAB}!$I$2:$I="")+({PLAN_TAB}!$I$2:$I>={month_cell})),0))'
    )


# --- Buchungen ------------------------------------------------------------------------------


def _transactions_tab_writes() -> list[TabWrite]:
    category = (
        '={"Kategorie";ARRAYFORMULA(IF(A2:A="",,IF(F2:F="","– offen –",'
        f'IFERROR(VLOOKUP(F2:F,{PLAN_TAB}!A:C,3,FALSE),"? unbekannte Planzeile"))))}}'
    )
    month = '={"Monat";ARRAYFORMULA(IF(B2:B="",,DATE(YEAR(B2:B),MONTH(B2:B),1)))}'
    return [
        TabWrite(f"{TRANSACTIONS_TAB}!A1:H1", [TRANSACTION_HEADERS], as_formulas=False),
        TabWrite(f"{TRANSACTIONS_TAB}!I1:J1", [[category, month]], as_formulas=True),
    ]


def _plan_line_dropdown(sheet_id: int) -> dict[str, Any]:
    return {
        "setDataValidation": {
            "range": _column_range(sheet_id, "F", first_row=1),
            "rule": {
                "condition": {
                    "type": "ONE_OF_RANGE",
                    "values": [{"userEnteredValue": f"={PLAN_TAB}!$A$2:$A"}],
                },
                "strict": False,
                "showCustomUi": True,
            },
        }
    }


# --- Auswertung -----------------------------------------------------------------------------


def _analysis_tab_writes(year: int) -> list[TabWrite]:
    last_month = (
        f"=IFERROR(DATE(YEAR(MAX({TRANSACTIONS_TAB}!B2:B)),MONTH(MAX({TRANSACTIONS_TAB}!B2:B)),1),"
        '"")'
    )
    writes = [
        TabWrite(f"{ANALYSIS_TAB}!A1:B1", [["Jahr", year]], as_formulas=False),
        TabWrite(f"{ANALYSIS_TAB}!A2:B2", [["Daten bis", last_month]], as_formulas=True),
    ]
    for title, start_row in ANALYSIS_BLOCK_STARTS.items():
        writes.append(_analysis_block(title, start_row))
    return writes


def _analysis_block(title: str, start_row: int) -> TabWrite:
    header_row = start_row + 1
    rows: list[list[SheetValue]] = [[title], _month_header("Kategorie", "Summe bis Stand")]
    for offset in range(CATEGORY_ROWS):
        row = header_row + 1 + offset
        rows.append(
            [
                _category_cell(title, offset),
                *[_analysis_cell(title, row, column, header_row) for column in MONTH_COLUMNS],
                f'=IF($A{row}="","",SUMIF($B${header_row}:$M${header_row},"<="&$B$2,B{row}:M{row}))',
            ]
        )
    end_row = header_row + CATEGORY_ROWS
    return TabWrite(f"{ANALYSIS_TAB}!A{start_row}:N{end_row}", rows, as_formulas=True)


def _month_header(first: str, last: str) -> list[SheetValue]:
    return [first, *[f"=DATE($B$1,{month},1)" for month in MONTHS], last]


def _category_cell(title: str, offset: int) -> str:
    """Only the first cell holds a formula; the categories spill down from it."""
    first_category_row = ANALYSIS_BLOCK_STARTS["Ist"] + 2
    if offset > 0:
        return ""
    if title == "Ist":
        return f'=UNIQUE(FILTER({PLAN_TAB}!C2:C,{PLAN_TAB}!C2:C<>""))'
    last_category_row = first_category_row + CATEGORY_ROWS - 1
    categories = f"A{first_category_row}:A{last_category_row}"
    return f'=ARRAYFORMULA(IF({categories}="","",{categories}))'


def _analysis_cell(title: str, row: int, column: str, header_row: int) -> str:
    month = f"{column}${header_row}"
    if title == "Ist":
        return f'=IF($A{row}="","",{_signed_actual(f"$A{row}", month)})'
    if title == "Plan":
        conditions = f"{PLAN_TAB}!$C$2:$C=$A{row}"
        return f'=IF($A{row}="","",{_plan_monthly_sum(conditions, month)})'
    return _difference_cell(row, column)


def _signed_actual(category_cell: str, month_cell: str) -> str:
    """Income counts positive, everything else as money spent."""
    return (
        f'IF({category_cell}="{INCOME_CATEGORY}",1,-1)*SUMIFS({TRANSACTIONS_TAB}!$C:$C,'
        f"{TRANSACTIONS_TAB}!$I:$I,{category_cell},{TRANSACTIONS_TAB}!$J:$J,{month_cell})"
    )


def _difference_cell(row: int, column: str) -> str:
    offset_in_block = row - ANALYSIS_BLOCK_STARTS["Ist − Plan"]
    actual_row = ANALYSIS_BLOCK_STARTS["Ist"] + offset_in_block
    plan_row = ANALYSIS_BLOCK_STARTS["Plan"] + offset_in_block
    return f'=IF($A{row}="","",{column}{actual_row}-{column}{plan_row})'


def _analysis_formats(sheet_id: int) -> list[dict[str, Any]]:
    formats = []
    for start_row in ANALYSIS_BLOCK_STARTS.values():
        header_row = start_row + 1
        first_value_row, last_value_row = header_row + 1, header_row + CATEGORY_ROWS
        formats.append(_cell_box_format(sheet_id, f"B{header_row}:M{header_row}", MONTH_FORMAT))
        formats.append(
            _cell_box_format(sheet_id, f"B{first_value_row}:N{last_value_row}", EURO_FORMAT)
        )
    return formats


# --- Planzeilen -----------------------------------------------------------------------------


def _plan_lines_tab_writes() -> list[TabWrite]:
    header_row = PLAN_LINES_FIRST_ROW - 1
    headers = [
        "ID", "Kategorie", "Beschreibung", "Topf", "Plan bis Stand", "Ist bis Stand",
        "Ist − Plan", "Plan ganzes Jahr", "Buchungen im Jahr",
    ]  # fmt: skip
    rows = [
        _plan_line_row(PLAN_LINES_FIRST_ROW + offset, offset) for offset in range(PLAN_LINE_ROWS)
    ]
    last_row = PLAN_LINES_FIRST_ROW + PLAN_LINE_ROWS - 1
    return [
        TabWrite(
            f"{PLAN_LINES_TAB}!A1:B2",
            [["Jahr", f"={ANALYSIS_TAB}!B1"], ["Daten bis", f"={ANALYSIS_TAB}!B2"]],
            as_formulas=True,
        ),
        TabWrite(f"{PLAN_LINES_TAB}!A{header_row}:I{header_row}", [headers], as_formulas=False),
        TabWrite(f"{PLAN_LINES_TAB}!A{PLAN_LINES_FIRST_ROW}:I{last_row}", rows, as_formulas=True),
    ]


def _plan_line_row(row: int, offset: int) -> list[SheetValue]:
    line = f"$A{row}"
    first_cell = f'=FILTER({PLAN_TAB}!A2:A,{PLAN_TAB}!A2:A<>"")' if offset == 0 else ""
    return [
        first_cell,
        _plan_lookup(line, 3),
        _plan_lookup(line, 4),
        _plan_lookup(line, 7),
        f'=IF(OR({line}="",$B$2=""),"",{_planned_for_months(line, "MONTH($B$2)")})',
        f'=IF({line}="","",{_signed_line_actual(line)})',
        f'=IF({line}="","",F{row}-E{row})',
        f'=IF({line}="","",{_planned_for_months(line, "12")})',
        f'=IF({line}="","",COUNTIFS({TRANSACTIONS_TAB}!$F:$F,{line},{_year_conditions()}))',
    ]


def _plan_lookup(line_cell: str, column_number: int) -> str:
    return f'=IF({line_cell}="","",VLOOKUP({line_cell},{PLAN_TAB}!$A:$J,{column_number},FALSE))'


def _planned_for_months(line_cell: str, month_count: str) -> str:
    """Pro Monat times the months of the year (up to `month_count`) the line is valid in.

    ARRAYFORMULA is required: without it LET keeps only the first month of the SEQUENCE.
    """
    lookup = f"{PLAN_TAB}!$A:$J"
    return (
        f"ARRAYFORMULA(LET(monthly,VLOOKUP({line_cell},{lookup},10,FALSE),"
        f"valid_from,VLOOKUP({line_cell},{lookup},8,FALSE),"
        f"valid_until,VLOOKUP({line_cell},{lookup},9,FALSE),"
        f"months,DATE($B$1,SEQUENCE({month_count}),1),"
        'monthly*SUMPRODUCT((months>=valid_from)*((valid_until="")+(months<=valid_until)>0))))'
    )


def _signed_line_actual(line_cell: str) -> str:
    return (
        f'IF(VLOOKUP({line_cell},{PLAN_TAB}!$A:$B,2,FALSE)="{INCOME_TYPE}",1,-1)'
        f"*SUMIFS({TRANSACTIONS_TAB}!$C:$C,{TRANSACTIONS_TAB}!$F:$F,{line_cell},"
        f'{TRANSACTIONS_TAB}!$J:$J,">="&DATE($B$1,1,1),{TRANSACTIONS_TAB}!$J:$J,"<="&$B$2)'
    )


def _year_conditions() -> str:
    return (
        f'{TRANSACTIONS_TAB}!$J:$J,">="&DATE($B$1,1,1),'
        f'{TRANSACTIONS_TAB}!$J:$J,"<"&DATE($B$1+1,1,1)'
    )


# --- Fixkosten-Topf -------------------------------------------------------------------------


def _fixed_costs_tab_writes() -> list[TabWrite]:
    header_row = FIXED_COSTS_FIRST_ROW - 1
    headers = [
        "Monat", "Plan-Rate (Topf Fixkosten)", "Eingezahlt", "Erstattet", "Saldo Monat",
        "Saldo kumuliert",
    ]  # fmt: skip
    rows = [
        _fixed_costs_row(FIXED_COSTS_FIRST_ROW + offset, month)
        for offset, month in enumerate(MONTHS)
    ]
    last_row = FIXED_COSTS_FIRST_ROW + len(MONTHS) - 1
    tab = f"'{FIXED_COSTS_TAB}'"
    return [
        TabWrite(f"{tab}!A1:B1", [["Jahr", f"={ANALYSIS_TAB}!B1"]], as_formulas=True),
        TabWrite(f"{tab}!A{header_row}:F{header_row}", [headers], as_formulas=False),
        TabWrite(f"{tab}!A{FIXED_COSTS_FIRST_ROW}:F{last_row}", rows, as_formulas=True),
    ]


def _fixed_costs_row(row: int, month: int) -> list[SheetValue]:
    month_cell = f"$A{row}"
    transfers = (
        f'{TRANSACTIONS_TAB}!$C:$C,{TRANSACTIONS_TAB}!$F:$F,"{FIXED_COSTS_TRANSFER_LINE}",'
        f"{TRANSACTIONS_TAB}!$J:$J,{month_cell},{TRANSACTIONS_TAB}!$C:$C"
    )
    pot_condition = f'{PLAN_TAB}!$G$2:$G="{FIXED_COSTS_POT}"'
    return [
        f"=DATE($B$1,{month},1)",
        f"={_plan_monthly_sum(pot_condition, month_cell)}",
        f'=-SUMIFS({transfers},"<0")',
        f'=SUMIFS({transfers},">0")',
        f"=C{row}-D{row}",
        f"=SUM($E${FIXED_COSTS_FIRST_ROW}:E{row})",
    ]


# --- Formats --------------------------------------------------------------------------------


def _header_requests(sheet_id: int, header_row: int) -> list[dict[str, Any]]:
    """`header_row` is 0-based; rows above it stay frozen with it."""
    return [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": header_row + 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row,
                    "endRowIndex": header_row + 1,
                },
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        },
    ]


def _number_format(
    sheet_id: int, column: str, number_format: dict[str, str], first_row: int = 1
) -> dict[str, Any]:
    """A whole column from the 0-based `first_row` down; the default skips the header row."""
    return _repeat_number_format(_column_range(sheet_id, column, first_row), number_format)


def _cell_box_format(sheet_id: int, a1_box: str, number_format: dict[str, str]) -> dict[str, Any]:
    """`a1_box` like `B5:M5`, in the notation the sheet shows."""
    top_left, bottom_right = a1_box.split(":")
    cell_range = {
        "sheetId": sheet_id,
        "startRowIndex": int(top_left[1:]) - 1,
        "endRowIndex": int(bottom_right[1:]),
        "startColumnIndex": _column_index(top_left[0]),
        "endColumnIndex": _column_index(bottom_right[0]) + 1,
    }
    return _repeat_number_format(cell_range, number_format)


def _repeat_number_format(cell_range: dict[str, int], number_format: dict[str, str]) -> dict:
    return {
        "repeatCell": {
            "range": cell_range,
            "cell": {"userEnteredFormat": {"numberFormat": number_format}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _column_range(sheet_id: int, column: str, first_row: int) -> dict[str, int]:
    index = _column_index(column)
    return {
        "sheetId": sheet_id,
        "startRowIndex": first_row,
        "startColumnIndex": index,
        "endColumnIndex": index + 1,
    }


def _column_index(column: str) -> int:
    return ord(column) - ord("A")
