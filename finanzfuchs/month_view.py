"""How a month is going: budgets with their pace, the fixed items to tick off, and the rest.

Pure: plan, transactions and today in, a `MonthView` out. The month page only formats it.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from finanzfuchs.ledger import LedgerEntry
from finanzfuchs.plan import FIXED, INCOME_TYPE, PlanLine

EXPENSE_TYPE = "Ausgabe"
MONTH_NAMES = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
               "September", "Oktober", "November", "Dezember")  # fmt: skip
PACE_TOLERANCE = Decimal("0.10")
"""A budget counts as too fast once it is 10 percentage points ahead of the month."""
FIXED_TOLERANCE_EUROS = Decimal(1)
FIXED_TOLERANCE_SHARE = Decimal("0.01")
RECENT_COUNT = 8
ZERO = Decimal(0)


@dataclass(frozen=True, order=True)
class Month:
    year: int
    month: int

    @classmethod
    def containing(cls, day: date) -> "Month":
        return cls(day.year, day.month)

    @classmethod
    def from_text(cls, text: str) -> "Month":
        """`2026-11`; raises ValueError for anything else."""
        year, month = (int(part) for part in text.split("-"))
        if not 1 <= month <= 12:
            raise ValueError(f"No month {month}")
        return cls(year, month)

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:
        return date(self.year, self.month, self.day_count)

    @property
    def day_count(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def label(self) -> str:
        return f"{MONTH_NAMES[self.month - 1]} {self.year}"

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}"

    def previous(self) -> "Month":
        return Month(self.year - 1, 12) if self.month == 1 else Month(self.year, self.month - 1)

    def next(self) -> "Month":
        return Month(self.year + 1, 1) if self.month == 12 else Month(self.year, self.month + 1)

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


class BudgetStatus(StrEnum):
    OK = "ok"
    FAST = "fast"
    OVER = "over"


class FixedStatus(StrEnum):
    RECEIVED = "received"
    DEVIATES = "deviates"
    PENDING = "pending"


@dataclass(frozen=True)
class Budget:
    line: PlanLine
    planned: Decimal
    spent: Decimal
    status: BudgetStatus

    @property
    def share(self) -> Decimal:
        return self.spent / self.planned

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent


@dataclass(frozen=True)
class FixedItem:
    line: PlanLine
    expected: Decimal
    actual: Decimal
    status: FixedStatus

    @property
    def is_income(self) -> bool:
        return self.line.line_type == INCOME_TYPE


@dataclass(frozen=True)
class PotItem:
    """Paid this month, but saved up over the year in the Fixkosten account."""

    line: PlanLine
    paid: Decimal


@dataclass(frozen=True)
class MonthView:
    month: Month
    progress: Decimal
    """Share of the month that has passed: 0 before it, 1 after it."""
    last_booking: date | None
    income: Decimal
    income_planned: Decimal
    spent: Decimal
    spent_planned: Decimal
    budgets: list[Budget]
    fixed_items: list[FixedItem]
    pot_items: list[PotItem]
    unplanned: list[LedgerEntry]
    recent: list[LedgerEntry]
    attention_count: int
    daily_budget_spending: list[Decimal] = field(default_factory=list)
    """Cumulative spending on the variable budgets per day, up to today or the month's end."""

    @property
    def remaining(self) -> Decimal:
        return self.spent_planned - self.spent

    @property
    def budget_planned(self) -> Decimal:
        return sum((budget.planned for budget in self.budgets), ZERO)

    @property
    def has_bookings(self) -> bool:
        return bool(self.recent)

    @property
    def days_left(self) -> int:
        passed = round(self.progress * self.month.day_count)
        return self.month.day_count - passed


def build_month_view(
    plan: list[PlanLine], entries: list[LedgerEntry], month: Month, today: date
) -> MonthView:
    lines = [line for line in plan if _is_valid_in(line, month)]
    lines_by_id = {line.plan_line_id: line for line in plan}
    in_month = [entry for entry in entries if month.contains(entry.transaction.booking_date)]
    progress = month_progress(month, today)
    budget_lines = [line for line in lines if _is_budget(line)]
    return MonthView(
        month=month,
        progress=progress,
        last_booking=max((e.transaction.booking_date for e in entries), default=None),
        income=_received_income(in_month, lines_by_id),
        income_planned=_planned_per_month(lines, INCOME_TYPE),
        spent=_monthly_spending(in_month, lines_by_id),
        spent_planned=_planned_per_month(lines, EXPENSE_TYPE),
        budgets=_budgets(budget_lines, in_month, progress),
        fixed_items=_fixed_items([line for line in lines if _is_fixed_item(line)], in_month),
        pot_items=_pot_items(
            [line for line in lines if line.is_paid_from_fixed_costs_pot], in_month
        ),
        unplanned=_unplanned(in_month, lines_by_id),
        recent=_newest_first(in_month)[:RECENT_COUNT],
        attention_count=sum(1 for entry in in_month if entry.needs_attention),
        daily_budget_spending=_daily_spending(budget_lines, in_month, month, today),
    )


def month_progress(month: Month, today: date) -> Decimal:
    if today < month.start:
        return ZERO
    if today > month.end:
        return Decimal(1)
    return Decimal(today.day) / Decimal(month.day_count)


def _budgets(lines: list[PlanLine], in_month: list[LedgerEntry], progress: Decimal) -> list[Budget]:
    budgets = []
    for line in lines:
        planned = _monthly(line)
        spent = _sum_for_line(line, in_month)
        budgets.append(Budget(line, planned, spent, _budget_status(planned, spent, progress)))
    return sorted(budgets, key=lambda budget: budget.planned, reverse=True)


def _budget_status(planned: Decimal, spent: Decimal, progress: Decimal) -> BudgetStatus:
    if spent > planned:
        return BudgetStatus.OVER
    if spent / planned > progress + PACE_TOLERANCE:
        return BudgetStatus.FAST
    return BudgetStatus.OK


def _fixed_items(lines: list[PlanLine], in_month: list[LedgerEntry]) -> list[FixedItem]:
    items = []
    for line in lines:
        expected = _monthly(line)
        line_entries = [e for e in in_month if e.plan_line_id == line.plan_line_id]
        actual = _sum_for_line(line, in_month)
        status = _fixed_status(line, expected, actual, line_entries)
        items.append(FixedItem(line, expected, actual, status))
    return sorted(items, key=lambda item: (not item.is_income, -item.expected))


def _fixed_status(
    line: PlanLine, expected: Decimal, actual: Decimal, line_entries: list[LedgerEntry]
) -> FixedStatus:
    """Income may be higher than planned; only less income, or a different debit, deviates."""
    if not line_entries:
        return FixedStatus.PENDING
    tolerance = max(FIXED_TOLERANCE_EUROS, expected * FIXED_TOLERANCE_SHARE)
    if line.line_type == INCOME_TYPE:
        is_as_planned = actual >= expected - tolerance
    else:
        is_as_planned = abs(actual - expected) <= tolerance
    return FixedStatus.RECEIVED if is_as_planned else FixedStatus.DEVIATES


def _pot_items(lines: list[PlanLine], in_month: list[LedgerEntry]) -> list[PotItem]:
    items = [PotItem(line, _sum_for_line(line, in_month)) for line in lines]
    return [item for item in items if item.paid != ZERO]


def _unplanned(in_month: list[LedgerEntry], lines_by_id: dict[str, PlanLine]) -> list[LedgerEntry]:
    """Spending on a line without a planned amount, or on no line yet."""

    def is_unplanned(entry: LedgerEntry) -> bool:
        line = lines_by_id.get(entry.plan_line_id or "")
        if line is None:
            return entry.transaction.amount < 0
        return line.line_type == EXPENSE_TYPE and line.amount == ZERO

    unplanned = [entry for entry in in_month if is_unplanned(entry)]
    return sorted(unplanned, key=lambda entry: entry.transaction.amount)


def _daily_spending(
    lines: list[PlanLine], in_month: list[LedgerEntry], month: Month, today: date
) -> list[Decimal]:
    last_day = month.day_count if today > month.end else (today.day if month.contains(today) else 0)
    budget_ids = {line.plan_line_id for line in lines}
    by_day = [ZERO] * (month.day_count + 1)
    for entry in in_month:
        if entry.plan_line_id in budget_ids:
            by_day[entry.transaction.booking_date.day] -= entry.transaction.amount
    running, cumulative = ZERO, []
    for day in range(1, last_day + 1):
        running += by_day[day]
        cumulative.append(running)
    return cumulative


def _is_valid_in(line: PlanLine, month: Month) -> bool:
    return line.valid_from <= month.end and (
        line.valid_until is None or line.valid_until >= month.start
    )


def _counts_monthly(line: PlanLine, line_type: str) -> bool:
    return line.line_type == line_type and not line.is_paid_from_fixed_costs_pot


def _is_budget(line: PlanLine) -> bool:
    return _counts_monthly(line, EXPENSE_TYPE) and line.kind != FIXED and line.amount > ZERO


def _is_fixed_item(line: PlanLine) -> bool:
    is_planned_flow = line.line_type in (INCOME_TYPE, EXPENSE_TYPE) and line.amount > ZERO
    return (
        is_planned_flow
        and not line.is_paid_from_fixed_costs_pot
        and (line.kind == FIXED or line.line_type == INCOME_TYPE)
    )


def _monthly(line: PlanLine) -> Decimal:
    """Only monthly lines reach here; yearly ones belong to the Fixkosten pot."""
    return line.amount


def _planned_per_month(lines: list[PlanLine], line_type: str) -> Decimal:
    return sum((_monthly(line) for line in lines if _counts_monthly(line, line_type)), ZERO)


def _received_income(in_month: list[LedgerEntry], lines_by_id: dict[str, PlanLine]) -> Decimal:
    income = [e for e in in_month if _is_income(e, lines_by_id)]
    return sum((e.transaction.amount for e in income), ZERO)


def _monthly_spending(in_month: list[LedgerEntry], lines_by_id: dict[str, PlanLine]) -> Decimal:
    spending = [e for e in in_month if _is_monthly_spending(e, lines_by_id)]
    return -sum((e.transaction.amount for e in spending), ZERO)


def _newest_first(entries: list[LedgerEntry]) -> list[LedgerEntry]:
    return sorted(entries, key=lambda entry: entry.transaction.booking_date, reverse=True)


def _sum_for_line(line: PlanLine, in_month: list[LedgerEntry]) -> Decimal:
    total = sum(
        (e.transaction.amount for e in in_month if e.plan_line_id == line.plan_line_id), ZERO
    )
    return total if line.line_type == INCOME_TYPE else -total


def _is_income(entry: LedgerEntry, lines_by_id: dict[str, PlanLine]) -> bool:
    line = lines_by_id.get(entry.plan_line_id or "")
    return line is not None and line.line_type == INCOME_TYPE


def _is_monthly_spending(entry: LedgerEntry, lines_by_id: dict[str, PlanLine]) -> bool:
    """Everything that left for a planned or unplanned expense, without the pot's yearly costs."""
    line = lines_by_id.get(entry.plan_line_id or "")
    if line is None:
        return entry.transaction.amount < 0
    return line.line_type == EXPENSE_TYPE and not line.is_paid_from_fixed_costs_pot
