"""The month page: how the current (or a chosen) month is going. It is the start page."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from finanzfuchs.month_view import Month, MonthView, build_month_view
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.session_store import SessionUser
from finanzfuchs.storage.transaction_store import TransactionStore
from finanzfuchs.web.context import TEMPLATES, Context, PageUser

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def current_month(request: Request, user: PageUser, context: Context) -> HTMLResponse:
    return _month_page(request, user, context, Month.containing(context.now().date()))


@router.get("/monat/{month_key}", response_class=HTMLResponse)
def chosen_month(
    request: Request, month_key: str, user: PageUser, context: Context
) -> HTMLResponse:
    try:
        month = Month.from_text(month_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=f"Kein Monat: {month_key}") from error
    return _month_page(request, user, context, month)


def _month_page(
    request: Request, user: SessionUser, context: Context, month: Month
) -> HTMLResponse:
    today = context.now().date()
    with context.database.connect() as connection:
        plan = PlanStore(connection).lines()
        transactions = TransactionStore(connection)
        entries = transactions.entries()
        attention = len(transactions.needing_attention())
    view = build_month_view(plan, entries, month, today)
    current = Month.containing(today)
    values = {
        "active": "month",
        "user": user,
        "attention": attention,
        "view": view,
        "is_current": month == current,
        "next_month": month.next() if month < current else None,
        "chart": _chart_data(view),
        "line_names": {line.plan_line_id: line.description for line in plan},
    }
    return TEMPLATES.TemplateResponse(request, "month.html", values)


def _chart_data(view: MonthView) -> dict[str, object]:
    """Cumulative budget spending per day against an even pace through the month."""
    days = view.month.day_count
    pace = [round(float(view.budget_planned) * day / days, 2) for day in range(1, days + 1)]
    return {
        "days": list(range(1, days + 1)),
        "actual": [round(float(amount), 2) for amount in view.daily_budget_spending],
        "pace": pace,
        "planned": round(float(view.budget_planned), 2),
    }
