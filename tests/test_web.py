from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from conftest import dkb_export, export_row, plan_line
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from finanzfuchs.assignment.rules import AssignmentRule
from finanzfuchs.config import Settings, WebSettings
from finanzfuchs.storage.database import Database
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.rule_store import RuleStore
from finanzfuchs.web.app import create_app
from finanzfuchs.web.context import SESSION_COOKIE
from finanzfuchs.web.oidc import LoginRequest, OidcError, VerifiedLogin
from finanzfuchs.web.plan_form import new_plan_line_id, parse_amount

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
WEB_SETTINGS = WebSettings(
    base_url="http://finanzfuchs.home",
    oidc_issuer="https://id.example.org",
    oidc_client_id="client",
    oidc_client_secret="secret",
    allowed_group="fuxbau",
    host="127.0.0.1",
    port=8000,
)
EXPORT = dkb_export(
    export_row("30.10.26", "REWE", "-20,30"), export_row("29.10.26", "IKEA", "-87,94")
)


class FakePocketId:
    """Answers like Pocket ID: any code but `bad` logs in the configured person."""

    def __init__(self, groups: frozenset[str] = frozenset({"fuxbau"})) -> None:
        self.groups = groups

    def start_login(self) -> LoginRequest:
        return LoginRequest(
            "state-1", "nonce-1", "verifier-1", "https://id.example.org/authorize?state=state-1"
        )

    def finish_login(self, code: str, code_verifier: str, nonce: str) -> VerifiedLogin:
        if code == "bad" or (code_verifier, nonce) != ("verifier-1", "nonce-1"):
            raise OidcError("token exchange failed")
        return VerifiedLogin("sub-merle", "Merle", self.groups)


def make_client(tmp_path: Path, provider: FakePocketId | None = None) -> TestClient:
    settings = Settings(data_dir=tmp_path, history_start=datetime(2026, 1, 1).date())
    app = create_app(settings, WEB_SETTINGS, provider or FakePocketId(), now=lambda: NOW)
    return TestClient(app, follow_redirects=False)


def log_in(client: TestClient) -> None:
    client.get("/auth/login")
    response = client.get("/auth/callback", params={"state": "state-1", "code": "ok"})
    assert response.status_code == 303


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    client = make_client(tmp_path)
    with Database(tmp_path / "finanzfuchs.sqlite3").connect() as connection:
        plans = PlanStore(connection)
        plans.add(plan_line("lebensmittel"))
        plans.add(plan_line("anschaffungen", category="Ungeplant", amount="0"))
        RuleStore(connection).append(AssignmentRule("lebensmittel", counterparty_contains="REWE"))
    return client


@pytest.fixture
def logged_in(client: TestClient) -> TestClient:
    log_in(client)
    return client


def upload(client: TestClient, content: str = EXPORT, name: str = "umsaetze.csv"):
    return client.post("/import", files={"file": (name, content.encode("utf-8"), "text/csv")})


class TestLogin:
    def test_pages_send_strangers_to_the_login(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_the_api_answers_strangers_with_401(self, client: TestClient) -> None:
        assert client.get("/api/attention").status_code == 401

    def test_login_goes_to_pocket_id(self, client: TestClient) -> None:
        response = client.get("/auth/login")

        assert response.headers["location"].startswith("https://id.example.org/authorize")

    def test_a_family_member_gets_an_http_only_session_cookie(self, client: TestClient) -> None:
        client.get("/auth/login")

        response = client.get("/auth/callback", params={"state": "state-1", "code": "ok"})

        cookie = response.headers["set-cookie"]
        assert SESSION_COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert client.get("/").status_code == 200

    def test_someone_outside_the_family_group_is_turned_away(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, FakePocketId(groups=frozenset({"friends"})))
        client.get("/auth/login")

        response = client.get("/auth/callback", params={"state": "state-1", "code": "ok"})

        assert response.status_code == 403
        assert SESSION_COOKIE not in response.headers.get("set-cookie", "")

    def test_a_callback_without_a_started_login_is_refused(self, client: TestClient) -> None:
        response = client.get("/auth/callback", params={"state": "forged", "code": "ok"})

        assert response.status_code == 403

    def test_a_failed_token_exchange_is_refused(self, client: TestClient) -> None:
        client.get("/auth/login")

        response = client.get("/auth/callback", params={"state": "state-1", "code": "bad"})

        assert response.status_code == 403

    def test_logout_ends_the_session(self, logged_in: TestClient) -> None:
        logged_in.post("/auth/logout")

        assert logged_in.get("/").status_code == 303

    def test_the_health_check_needs_no_login(self, client: TestClient) -> None:
        assert client.get("/healthz").text == "ok"


class TestPages:
    def test_the_overview_is_the_dashboard_with_navigation(self, logged_in: TestClient) -> None:
        html = logged_in.get("/").text

        assert "window.BAUPLAN_DATA" in html
        assert 'href="/zuordnen"' in html and "Merle" in html

    def test_an_import_reports_what_was_added_and_assigned(self, logged_in: TestClient) -> None:
        response = upload(logged_in)

        assert response.status_code == 200
        assert "umsaetze.csv" in response.text
        assert "Jetzt 1 zuordnen" in response.text

    def test_an_import_of_a_foreign_file_explains_the_problem(self, logged_in: TestClient) -> None:
        response = upload(logged_in, content="Name;Betrag\nfoo;1\n", name="falsch.csv")

        assert response.status_code == 400
        assert "kein DKB-Umsatzexport" in response.text

    def test_the_plan_page_lists_every_line(self, logged_in: TestClient) -> None:
        html = logged_in.get("/plan").text

        assert 'id="lebensmittel"' in html and 'id="anschaffungen"' in html

    def test_saving_a_plan_line_changes_amount_and_validity(
        self, logged_in: TestClient, tmp_path: Path
    ) -> None:
        form = {
            "description": "Lebensmittel",
            "category": "Täglicher Bedarf",
            "line_type": "Ausgabe",
            "amount": "1.050,50",
            "rhythm": "Monat",
            "pot": "",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
        }

        response = logged_in.post("/plan/lebensmittel", data=form)

        assert response.status_code == 303
        with Database(tmp_path / "finanzfuchs.sqlite3").connect() as connection:
            line = PlanStore(connection).get("lebensmittel")
        assert line is not None
        assert (line.amount, line.valid_until.isoformat()) == (Decimal("1050.50"), "2026-12-31")

    def test_a_plan_line_with_a_broken_amount_is_not_saved(self, logged_in: TestClient) -> None:
        form = {"description": "Lebensmittel", "category": "x", "line_type": "Ausgabe",
                "amount": "viel", "rhythm": "Monat", "valid_from": "2026-01-01"}  # fmt: skip

        response = logged_in.post("/plan/lebensmittel", data=form)

        assert response.status_code == 400
        assert "keine Zahl" in response.text

    def test_a_new_plan_line_gets_an_id_from_its_description(self, logged_in: TestClient) -> None:
        form = {"description": "Kita Essen", "category": "Fixkosten", "line_type": "Ausgabe",
                "amount": "45", "rhythm": "Monat", "valid_from": "2026-11-01"}  # fmt: skip

        response = logged_in.post("/plan/neu", data=form)

        assert response.headers["location"] == "/plan?saved=kita-essen"

    def test_the_export_is_an_excel_file(self, logged_in: TestClient) -> None:
        upload(logged_in)

        response = logged_in.get("/export.xlsx")

        workbook = load_workbook(BytesIO(response.content))
        assert workbook["Buchungen"].max_row == 3


class TestAssignApi:
    def test_lists_what_needs_attention_with_the_plan_lines(self, logged_in: TestClient) -> None:
        upload(logged_in)

        data = logged_in.get("/api/attention").json()

        assert [entry["counterparty"] for entry in data["entries"]] == ["IKEA"]
        assert {line["id"] for line in data["planLines"]} == {"lebensmittel", "anschaffungen"}

    def test_assigning_by_hand_reports_what_is_left(self, logged_in: TestClient) -> None:
        upload(logged_in)
        [ikea] = logged_in.get("/api/attention").json()["entries"]

        response = logged_in.post(
            f"/api/transactions/{ikea['id']}/assign",
            json={"plan_line_id": "anschaffungen", "remember": True},
        )

        assert response.json() == {"ruleCreated": True, "alsoAssigned": 0, "remaining": 0}

    def test_assigning_to_an_unknown_plan_line_fails(self, logged_in: TestClient) -> None:
        upload(logged_in)
        [ikea] = logged_in.get("/api/attention").json()["entries"]

        response = logged_in.post(
            f"/api/transactions/{ikea['id']}/assign", json={"plan_line_id": "nope"}
        )

        assert response.status_code == 404

    def test_confirming_an_open_transaction_fails(self, logged_in: TestClient) -> None:
        upload(logged_in)
        [ikea] = logged_in.get("/api/attention").json()["entries"]

        assert logged_in.post(f"/api/transactions/{ikea['id']}/confirm").status_code == 404


class TestPlanForm:
    @pytest.mark.parametrize("text", ["1.409,84", "1409,84", "1409.84", "1.409,84 €"])
    def test_reads_german_and_plain_amounts(self, text: str) -> None:
        assert parse_amount(text) == Decimal("1409.84")

    def test_new_ids_never_collide(self) -> None:
        assert new_plan_line_id("Kita Essen", {"kita-essen", "kita-essen-2"}) == "kita-essen-3"

    def test_ids_spell_out_umlauts(self) -> None:
        assert new_plan_line_id("Gebühren & Steuern", set()) == "gebuehren-steuern"
