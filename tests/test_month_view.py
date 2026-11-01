from datetime import date
from decimal import Decimal

import pytest

from finanzfuchs.banking.transactions import BankTransaction
from finanzfuchs.ledger import AssignmentSource, LedgerEntry
from finanzfuchs.month_view import (
    BudgetStatus,
    FixedStatus,
    Month,
    build_month_view,
    month_progress,
)
from finanzfuchs.plan import FIXED, VARIABLE, PlanLine

NOVEMBER = Month(2026, 11)


def line(
    plan_line_id: str,
    amount: str,
    kind: str = VARIABLE,
    line_type: str = "Ausgabe",
    rhythm: str = "Monat",
    pot: str = "",
    valid_until: date | None = None,
) -> PlanLine:
    description = plan_line_id.capitalize()
    return PlanLine(plan_line_id, line_type, "Kategorie", description, Decimal(amount),
                    rhythm, pot, date(2026, 1, 1), valid_until, kind)  # fmt: skip


def booking(day: date, amount: str, plan_line_id: str | None, note: str = "") -> LedgerEntry:
    transaction = BankTransaction(f"t-{day}-{amount}-{plan_line_id}", "DE01", day, Decimal(amount),
                                  "Gegenseite", "DE02", "Zweck", True)  # fmt: skip
    source = AssignmentSource.RULE if plan_line_id else AssignmentSource.OPEN
    return LedgerEntry(transaction, plan_line_id, source, note)


FOOD = line("lebensmittel", "800")
RENT = line("miete", "1200", kind=FIXED)
SALARY = line("gehalt", "3000", kind=FIXED, line_type="Einnahme")
TV_FEE = line("gez", "220", kind=FIXED, rhythm="Jahr")
CATS = line("katzen", "150", kind=FIXED, pot="Fixkosten")
EXTRAS = line("ungeplant", "0")
PLAN = [FOOD, RENT, SALARY, TV_FEE, CATS, EXTRAS]


def view(entries: list[LedgerEntry], today: date = date(2026, 11, 15), plan=PLAN):
    return build_month_view(plan, entries, NOVEMBER, today)


class TestMonth:
    def test_knows_its_days_and_neighbours(self) -> None:
        assert (Month(2026, 2).day_count, Month(2028, 2).day_count) == (28, 29)
        assert (Month(2026, 1).previous(), Month(2026, 12).next()) == (
            Month(2025, 12),
            Month(2027, 1),
        )

    def test_reads_its_key_and_shows_a_german_label(self) -> None:
        assert Month.from_text("2026-11") == NOVEMBER
        assert (NOVEMBER.key, NOVEMBER.label) == ("2026-11", "November 2026")

    @pytest.mark.parametrize("text", ["2026-13", "november", "2026"])
    def test_rejects_anything_but_year_dash_month(self, text: str) -> None:
        with pytest.raises(ValueError):
            Month.from_text(text)

    def test_progress_runs_from_zero_before_to_one_after_the_month(self) -> None:
        assert month_progress(NOVEMBER, date(2026, 10, 31)) == 0
        assert month_progress(NOVEMBER, date(2026, 11, 15)) == Decimal("0.5")
        assert month_progress(NOVEMBER, date(2026, 12, 1)) == 1


class TestTotals:
    def test_compares_income_and_spending_with_the_monthly_plan(self) -> None:
        result = view([booking(date(2026, 11, 1), "3000", "gehalt"),
                       booking(date(2026, 11, 3), "-1200", "miete"),
                       booking(date(2026, 11, 4), "-100", "lebensmittel")])  # fmt: skip

        assert (result.income, result.income_planned) == (Decimal(3000), Decimal(3000))
        assert (result.spent, result.spent_planned) == (Decimal(1300), Decimal(2000))
        assert result.remaining == Decimal(700)

    def test_yearly_costs_from_the_pot_stay_out_of_the_month(self) -> None:
        result = view(
            [booking(date(2026, 11, 2), "-220", "gez"), booking(date(2026, 11, 2), "-40", "katzen")]
        )

        assert result.spent == 0
        assert [(item.line.plan_line_id, item.paid) for item in result.pot_items] == [
            ("gez", Decimal(220)), ("katzen", Decimal(40))]  # fmt: skip

    def test_open_transactions_count_as_spent_and_unplanned(self) -> None:
        open_one = booking(date(2026, 11, 5), "-30", None)

        result = view([open_one])

        assert result.spent == Decimal(30)
        assert result.unplanned == [open_one]
        assert result.attention_count == 1

    def test_ignores_other_months(self) -> None:
        result = view([booking(date(2026, 10, 31), "-500", "lebensmittel")])

        assert result.spent == 0
        assert not result.has_bookings
        assert result.last_booking == date(2026, 10, 31)


class TestBudgets:
    def budget(self, spent: str, today: date):
        result = view([booking(date(2026, 11, 2), f"-{spent}", "lebensmittel")], today=today)
        [budget] = result.budgets
        return budget

    def test_within_pace_is_ok(self) -> None:
        budget = self.budget("400", today=date(2026, 11, 15))

        assert budget.status == BudgetStatus.OK
        assert budget.remaining == Decimal(400)

    def test_ten_points_ahead_of_the_month_is_too_fast(self) -> None:
        assert self.budget("490", today=date(2026, 11, 15)).status == BudgetStatus.FAST

    def test_more_than_planned_is_over(self) -> None:
        assert self.budget("801", today=date(2026, 11, 30)).status == BudgetStatus.OVER

    def test_fixed_and_unplanned_lines_are_no_budgets(self) -> None:
        assert [budget.line.plan_line_id for budget in view([]).budgets] == ["lebensmittel"]

    def test_refunds_reduce_what_was_spent(self) -> None:
        result = view([booking(date(2026, 11, 2), "-100", "lebensmittel"),
                       booking(date(2026, 11, 3), "20", "lebensmittel")])  # fmt: skip

        assert result.budgets[0].spent == Decimal(80)


class TestFixedItems:
    def items(self, *entries: LedgerEntry) -> dict[str, FixedStatus]:
        return {item.line.plan_line_id: item.status for item in view(list(entries)).fixed_items}

    def test_lists_income_before_spending(self) -> None:
        assert list(self.items()) == ["gehalt", "miete"]

    def test_not_yet_booked_is_pending(self) -> None:
        assert self.items() == {"gehalt": FixedStatus.PENDING, "miete": FixedStatus.PENDING}

    def test_the_expected_amount_is_received(self) -> None:
        statuses = self.items(booking(date(2026, 11, 3), "-1200", "miete"))

        assert statuses["miete"] == FixedStatus.RECEIVED

    def test_a_different_amount_deviates(self) -> None:
        statuses = self.items(booking(date(2026, 11, 3), "-1250", "miete"))

        assert statuses["miete"] == FixedStatus.DEVIATES

    def test_lines_that_ended_before_the_month_are_left_out(self) -> None:
        ended = line("alt", "50", kind=FIXED, valid_until=date(2026, 10, 31))

        result = view([], plan=[*PLAN, ended])

        assert "alt" not in {item.line.plan_line_id for item in result.fixed_items}


class TestDailySpending:
    def test_accumulates_budget_spending_up_to_today(self) -> None:
        result = view(
            [booking(date(2026, 11, 1), "-50", "lebensmittel"),
             booking(date(2026, 11, 3), "-25", "lebensmittel"),
             booking(date(2026, 11, 3), "-1200", "miete")],
            today=date(2026, 11, 4),
        )  # fmt: skip

        assert result.daily_budget_spending == [Decimal(50), Decimal(50), Decimal(75), Decimal(75)]

    def test_a_past_month_runs_to_its_last_day(self) -> None:
        assert len(view([], today=date(2026, 12, 5)).daily_budget_spending) == 30

    def test_a_future_month_has_no_days_yet(self) -> None:
        assert view([], today=date(2026, 10, 5)).daily_budget_spending == []


class TestFixedIncome:
    def test_more_income_than_planned_counts_as_received(self) -> None:
        result = view([booking(date(2026, 11, 1), "3400", "gehalt")])

        [salary] = [item for item in result.fixed_items if item.is_income]
        assert salary.status == FixedStatus.RECEIVED

    def test_less_income_than_planned_deviates(self) -> None:
        result = view([booking(date(2026, 11, 1), "2500", "gehalt")])

        [salary] = [item for item in result.fixed_items if item.is_income]
        assert salary.status == FixedStatus.DEVIATES
