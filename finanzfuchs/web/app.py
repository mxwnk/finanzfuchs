"""The Finanzfuchs web app: wiring settings, database, login and routes together."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from finanzfuchs.config import Settings, WebSettings
from finanzfuchs.storage.database import Database
from finanzfuchs.web import api_routes, login_routes, month_routes, page_routes
from finanzfuchs.web.auth import Clock, IdentityProvider, LoginFlow, utc_now
from finanzfuchs.web.context import AppContext, LoginRequiredError
from finanzfuchs.web.oidc import OidcClient, OidcClientConfig

STATIC_DIR = Path(__file__).parent / "static"
# ECharts as a cached file for the month page; the year page inlines it.
VENDOR_DIR = Path(__file__).parent.parent / "dashboard" / "vendor"


def create_app(
    settings: Settings,
    web_settings: WebSettings,
    provider: IdentityProvider | None = None,
    now: Clock = utc_now,
) -> FastAPI:
    database = Database(settings.database_path)
    database.initialize()
    login_flow = LoginFlow(provider or _pocket_id(web_settings), database,
                           web_settings.allowed_group, now)  # fmt: skip

    app = FastAPI(title="Finanzfuchs", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.context = AppContext(settings, web_settings, database, login_flow, now)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/vendor", StaticFiles(directory=VENDOR_DIR), name="vendor")
    app.include_router(login_routes.router)
    app.include_router(month_routes.router)
    app.include_router(page_routes.router)
    app.include_router(api_routes.router)
    app.add_exception_handler(LoginRequiredError, _redirect_to_login)
    app.add_api_route("/healthz", _health, methods=["GET"], response_class=PlainTextResponse)
    return app


def _pocket_id(web_settings: WebSettings) -> OidcClient:
    return OidcClient(
        OidcClientConfig(
            issuer=web_settings.oidc_issuer,
            client_id=web_settings.oidc_client_id,
            client_secret=web_settings.oidc_client_secret,
            redirect_uri=web_settings.redirect_uri,
        )
    )


def _redirect_to_login(request: Request, error: Exception) -> RedirectResponse:
    return RedirectResponse("/auth/login", status_code=303)


def _health() -> str:
    return "ok"
