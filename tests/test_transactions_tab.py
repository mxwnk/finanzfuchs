from datetime import date
from decimal import Decimal

from bauplan.assignment.rules import Assignment
from bauplan.banking.transactions import BankTransaction
from bauplan.sheets.transactions_tab import (
    CellFill,
    plan_transaction_changes,
    to_sheet_date,
    transaction_row,
)


def transaction(transaction_id: str, booking_date: date = date(2026, 3, 2)) -> BankTransaction:
    return BankTransaction(
        transaction_id=transaction_id,
        account_uid="DE01",
        booking_date=booking_date,
        amount=Decimal("-61.07"),
        counterparty_name="Sky",
        counterparty_iban="DE11",
        purpose="=HYPERLINK(1)",
        is_booked=True,
    )


def by_rule(transaction_id: str, booking_date: date = date(2026, 3, 2)) -> Assignment:
    return Assignment(transaction(transaction_id, booking_date), "sky-abo", 7, "Abo")


def open_assignment(transaction_id: str) -> Assignment:
    return Assignment(transaction(transaction_id), None, None)


def sheet_row(transaction_id: str, plan_line_id: str = "", source: str = "") -> list[object]:
    return [transaction_id, 46083, -61.07, "Sky", "Abo", plan_line_id, source, ""]


def test_sheet_dates_count_days_like_spreadsheets() -> None:
    assert to_sheet_date(date(1899, 12, 31)) == 1
    assert to_sheet_date(date(2026, 1, 1)) == 46023


def test_a_row_carries_the_assignment_and_its_source() -> None:
    row = transaction_row(by_rule("t1"))

    assert row == ["t1", 46083, -61.07, "Sky", "=HYPERLINK(1)", "sky-abo", "Regel 7", "Abo"]


def test_an_open_transaction_leaves_the_plan_line_empty() -> None:
    row = transaction_row(open_assignment("t1"))

    assert row[5:] == ["", "", ""]


def test_appends_only_transactions_the_sheet_does_not_hold() -> None:
    changes = plan_transaction_changes([sheet_row("t1", "sky-abo")], [by_rule("t1"), by_rule("t2")])

    assert [row[0] for row in changes.new_rows] == ["t2"]


def test_appends_new_transactions_in_date_order() -> None:
    later, earlier = by_rule("late", date(2026, 5, 1)), by_rule("early", date(2026, 1, 2))

    changes = plan_transaction_changes([], [later, earlier])

    assert [row[0] for row in changes.new_rows] == ["early", "late"]


def test_fills_an_empty_plan_line_once_a_rule_matches() -> None:
    existing = [sheet_row("t1", "lebensmittel"), sheet_row("t2")]

    changes = plan_transaction_changes(existing, [by_rule("t1"), by_rule("t2")])

    assert changes.cell_fills == [CellFill(row_number=3, values=["sky-abo", "Regel 7", "Abo"])]


def test_never_overwrites_a_plan_line_chosen_by_hand() -> None:
    existing = [sheet_row("t1", "ungeplant-sonstiges", source="")]

    changes = plan_transaction_changes(existing, [by_rule("t1")])

    assert changes.cell_fills == []


def test_leaves_rows_alone_that_no_rule_matches() -> None:
    changes = plan_transaction_changes([sheet_row("t1")], [open_assignment("t1")])

    assert changes.cell_fills == []
    assert changes.new_rows == []


def test_tolerates_short_rows_the_sheet_api_returns_for_empty_cells() -> None:
    changes = plan_transaction_changes([["t1", 46083, -61.07]], [by_rule("t1")])

    assert changes.cell_fills == [CellFill(row_number=2, values=["sky-abo", "Regel 7", "Abo"])]
