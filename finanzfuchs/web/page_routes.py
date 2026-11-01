"""The HTML pages: year overview, assigning, import, plan and the Excel export."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from finanzfuchs.dashboard.dataset import build_dataset
from finanzfuchs.dashboard.render import render_dashboard
from finanzfuchs.export import build_workbook
from finanzfuchs.importing import import_dkb_export
from finanzfuchs.imports.dkb_csv import DkbExportError
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.session_store import SessionUser
from finanzfuchs.storage.transaction_store import TransactionStore
from finanzfuchs.web.context import TEMPLATES, AppContext, Context, PageUser
from finanzfuchs.web.plan_form import PlanFormError, new_plan_line_id, plan_line_from_form

RECENT_IMPORTS = 8
EXPORT_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter()


@router.get("/jahr", response_class=HTMLResponse)
def year_overview(user: PageUser, context: Context) -> HTMLResponse:
    with context.database.connect() as connection:
        plan = PlanStore(connection).lines()
        entries = TransactionStore(connection).entries()
    attention = sum(1 for entry in entries if entry.needs_attention)
    nav = _render_nav("year", user, attention)
    return HTMLResponse(render_dashboard(build_dataset(plan, entries, context.now()), nav))


@router.get("/zuordnen", response_class=HTMLResponse)
def assign_page(
    request: Request,
    user: PageUser,
    context: Context,
) -> HTMLResponse:
    return _page(request, "assign.html", "assign", user, context)


@router.get("/import", response_class=HTMLResponse)
def import_page(
    request: Request,
    user: PageUser,
    context: Context,
) -> HTMLResponse:
    return _page(request, "import.html", "import", user, context)


@router.post("/import", response_class=HTMLResponse)
async def import_upload(
    request: Request,
    file: UploadFile,
    user: PageUser,
    context: Context,
) -> HTMLResponse:
    text = _decode_export(await file.read())
    try:
        with context.database.connect() as connection:
            summary = import_dkb_export(
                connection, text, file.filename or "export.csv", user.name, context.now()
            )
    except DkbExportError as error:
        return _page(request, "import.html", "import", user, context, status_code=400,
                     error=f"Die Datei ist kein DKB-Umsatzexport: {error}")  # fmt: skip
    return _page(request, "import.html", "import", user, context, summary=summary)


@router.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request, user: PageUser, context: Context, saved: str = "") -> HTMLResponse:
    return _page(request, "plan.html", "plan", user, context, saved=saved)


@router.post("/plan/neu", response_model=None)
async def add_plan_line(
    request: Request,
    user: PageUser,
    context: Context,
) -> Response:
    form = dict(await request.form())
    with context.database.connect() as connection:
        store = PlanStore(connection)
        existing_ids = {line.plan_line_id for line in store.lines()}
        try:
            line = plan_line_from_form(
                new_plan_line_id(str(form.get("description", "")), existing_ids), form
            )
        except PlanFormError as error:
            return _page(
                request, "plan.html", "plan", user, context, status_code=400, error=str(error)
            )
        store.add(line)
    return RedirectResponse(f"/plan?saved={line.plan_line_id}", status_code=303)


@router.post("/plan/{plan_line_id}", response_model=None)
async def update_plan_line(
    request: Request,
    plan_line_id: str,
    user: PageUser,
    context: Context,
) -> Response:
    form = dict(await request.form())
    with context.database.connect() as connection:
        store = PlanStore(connection)
        if store.get(plan_line_id) is None:
            return _page(request, "plan.html", "plan", user, context, status_code=404,
                         error=f"Planzeile {plan_line_id} gibt es nicht.")  # fmt: skip
        try:
            store.update(plan_line_from_form(plan_line_id, form))
        except PlanFormError as error:
            return _page(
                request, "plan.html", "plan", user, context, status_code=400, error=str(error)
            )
    return RedirectResponse(f"/plan?saved={plan_line_id}", status_code=303)


@router.get("/export.xlsx")
def export(user: PageUser, context: Context) -> Response:
    with context.database.connect() as connection:
        content = build_workbook(
            PlanStore(connection).lines(), TransactionStore(connection).entries()
        )
    file_name = f"finanzfuchs-{date.today().isoformat()}.xlsx"
    disposition = f'attachment; filename="{file_name}"'
    return Response(
        content, media_type=EXPORT_MEDIA_TYPE, headers={"Content-Disposition": disposition}
    )


def _page(
    request: Request,
    template: str,
    active: str,
    user: SessionUser,
    context: AppContext,
    status_code: int = 200,
    **values: Any,
) -> HTMLResponse:
    with context.database.connect() as connection:
        plan = PlanStore(connection).lines()
        transactions = TransactionStore(connection)
        attention = len(transactions.needing_attention())
        imports = transactions.latest_imports(RECENT_IMPORTS)
    page_values = {"active": active, "user": user, "attention": attention, "plan": plan,
                   "imports": imports, "today": date.today().isoformat(), **values}  # fmt: skip
    return TEMPLATES.TemplateResponse(request, template, page_values, status_code=status_code)


def _render_nav(active: str, user: SessionUser, attention: int) -> str:
    return TEMPLATES.get_template("_nav.html").render(active=active, user=user, attention=attention)


def _decode_export(content: bytes) -> str:
    """Today's DKB exports are UTF-8; older ones came as Windows-1252."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252")
