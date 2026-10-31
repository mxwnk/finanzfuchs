"""The three login endpoints: off to Pocket ID, back from it, and logout."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from finanzfuchs.config import CALLBACK_PATH
from finanzfuchs.web.auth import SESSION_LIFETIME, LoginRejectedError
from finanzfuchs.web.context import SESSION_COOKIE, TEMPLATES, Context

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/auth/login")
def login(context: Context) -> RedirectResponse:
    return RedirectResponse(context.login_flow.start(), status_code=303)


@router.get(CALLBACK_PATH)
def callback(request: Request, context: Context, state: str = "", code: str = "") -> Response:
    try:
        token = context.login_flow.finish(state, code)
    except LoginRejectedError as error:
        logger.warning("Login rejected: %s", error)
        return TEMPLATES.TemplateResponse(request, "login_denied.html", status_code=403)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=context.web_settings.uses_https,
    )
    return response


@router.post("/auth/logout")
def logout(request: Request, context: Context) -> HTMLResponse:
    context.login_flow.logout(request.cookies.get(SESSION_COOKIE))
    response = TEMPLATES.TemplateResponse(request, "logged_out.html")
    response.delete_cookie(SESSION_COOKIE)
    return response
