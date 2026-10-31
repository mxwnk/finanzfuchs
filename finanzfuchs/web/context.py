"""What every request handler needs, and the login checks in front of pages and the API."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates

from finanzfuchs.config import Settings, WebSettings
from finanzfuchs.storage.database import Database
from finanzfuchs.storage.session_store import SessionUser
from finanzfuchs.web.auth import Clock, LoginFlow

SESSION_COOKIE = "finanzfuchs_session"
TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    web_settings: WebSettings
    database: Database
    login_flow: LoginFlow
    now: Clock


class LoginRequiredError(Exception):
    """A page was asked for without a session; the handler sends the browser to the login."""


def app_context(request: Request) -> AppContext:
    return request.app.state.context


def page_user(request: Request) -> SessionUser:
    user = _session_user(request)
    if user is None:
        raise LoginRequiredError()
    return user


def api_user(request: Request) -> SessionUser:
    user = _session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    return user


def _session_user(request: Request) -> SessionUser | None:
    return app_context(request).login_flow.user_for(request.cookies.get(SESSION_COOKIE))


# Parameter types for the route handlers: the login check and the context come injected.
Context = Annotated[AppContext, Depends(app_context)]
PageUser = Annotated[SessionUser, Depends(page_user)]
ApiUser = Annotated[SessionUser, Depends(api_user)]
