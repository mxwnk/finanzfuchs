import json
from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from finanzfuchs.banking.client import API_BASE_URL, EnableBankingClient, EnableBankingError

NOW = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def make_client(private_key_pem: str) -> Callable[[Handler], EnableBankingClient]:
    def build(handler: Handler) -> EnableBankingClient:
        http_client = httpx.Client(base_url=API_BASE_URL, transport=httpx.MockTransport(handler))
        return EnableBankingClient("app-id", private_key_pem, http_client, clock=lambda: NOW)

    return build


def test_signs_every_request_with_a_bearer_token(make_client) -> None:
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["Authorization"])
        return httpx.Response(200, json={"aspsps": [{"name": "DKB", "country": "DE"}]})

    make_client(handler).find_bank("DKB", "DE")

    assert seen_headers[0].startswith("Bearer ey")


def test_finds_the_bank_by_name_ignoring_case(make_client) -> None:
    banks = [{"name": "DKB", "country": "DE"}, {"name": "Sparkasse", "country": "DE"}]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["country"] == "DE"
        return httpx.Response(200, json={"aspsps": banks})

    bank = make_client(handler).find_bank("dkb", "DE")

    assert bank["name"] == "DKB"


def test_lists_similar_banks_when_the_name_is_unknown(make_client) -> None:
    banks = [{"name": "DKB AG", "country": "DE"}, {"name": "Sparkasse", "country": "DE"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"aspsps": banks})

    with pytest.raises(EnableBankingError, match="DKB AG"):
        make_client(handler).find_bank("DKB", "DE")


def test_starts_the_authorization_for_personal_accounts(make_client) -> None:
    sent_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"url": "https://bank/approve", "authorization_id": "a1"})

    consent_end = datetime(2027, 4, 30, tzinfo=UTC)
    approval_url = make_client(handler).start_authorization(
        bank={"name": "DKB", "country": "DE"},
        consent_end=consent_end,
        state="state-1",
        redirect_url="https://example.org/finanzfuchs/callback",
    )

    assert approval_url == "https://bank/approve"
    assert sent_bodies[0] == {
        "access": {"valid_until": "2027-04-30T00:00:00+00:00"},
        "aspsp": {"name": "DKB", "country": "DE"},
        "state": "state-1",
        "redirect_url": "https://example.org/finanzfuchs/callback",
        "psu_type": "personal",
    }


def test_follows_continuation_keys_until_the_last_page(make_client) -> None:
    requested_keys: list[str | None] = []
    pages = {
        None: {"transactions": [{"transaction_id": "1"}], "continuation_key": "page-2"},
        "page-2": {"transactions": [{"transaction_id": "2"}], "continuation_key": None},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.params.get("continuation_key")
        requested_keys.append(key)
        assert request.url.path == "/accounts/uid-1/transactions"
        assert request.url.params["date_from"] == "2026-01-01"
        return httpx.Response(200, json=pages[key])

    fetched_pages = make_client(handler).fetch_transaction_pages("uid-1", date(2026, 1, 1))

    assert requested_keys == [None, "page-2"]
    assert [page["transactions"][0]["transaction_id"] for page in fetched_pages] == ["1", "2"]


def test_reports_status_and_body_of_a_failed_request(make_client) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Expired session"})

    with pytest.raises(EnableBankingError) as raised:
        make_client(handler).fetch_balances("uid-1")

    message = str(raised.value)
    assert "401" in message
    assert "/accounts/uid-1/balances" in message
    assert "Expired session" in message
