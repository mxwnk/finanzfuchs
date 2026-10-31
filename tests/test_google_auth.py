import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bauplan.sheets.google_auth import (
    SHEETS_SCOPE,
    GoogleAuthError,
    ServiceAccount,
    ServiceAccountTokens,
)

NOW = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
TOKEN_URI = "https://oauth2.googleapis.com/token"


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def account(private_key_pem: str) -> ServiceAccount:
    return ServiceAccount(
        client_email="bauplan@fuxbau.iam.gserviceaccount.com",
        private_key_pem=private_key_pem,
        token_uri=TOKEN_URI,
    )


def tokens_answering(account: ServiceAccount, handler, clock=lambda: NOW) -> ServiceAccountTokens:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return ServiceAccountTokens(account, http_client, clock=clock)


def token_response(access_token: str = "token-1", expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(200, json={"access_token": access_token, "expires_in": expires_in})


class TestServiceAccount:
    def test_reads_the_key_file_google_hands_out(
        self, tmp_path: Path, private_key_pem: str
    ) -> None:
        key_file = tmp_path / "key.json"
        key_file.write_text(
            json.dumps(
                {
                    "type": "service_account",
                    "client_email": "bauplan@fuxbau.iam.gserviceaccount.com",
                    "private_key": private_key_pem,
                    "token_uri": TOKEN_URI,
                }
            )
        )

        account = ServiceAccount.from_key_file(key_file)

        assert account.client_email == "bauplan@fuxbau.iam.gserviceaccount.com"
        assert account.token_uri == TOKEN_URI

    def test_rejects_a_file_that_is_no_service_account_key(self, tmp_path: Path) -> None:
        key_file = tmp_path / "key.json"
        key_file.write_text(json.dumps({"type": "authorized_user"}))

        with pytest.raises(GoogleAuthError, match="service account"):
            ServiceAccount.from_key_file(key_file)

    def test_reports_a_missing_key_file(self, tmp_path: Path) -> None:
        with pytest.raises(GoogleAuthError, match="missing.json"):
            ServiceAccount.from_key_file(tmp_path / "missing.json")


class TestServiceAccountTokens:
    def test_exchanges_a_signed_assertion_for_an_access_token(
        self, account: ServiceAccount
    ) -> None:
        sent_forms: list[dict[str, list[str]]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent_forms.append(parse_qs(request.content.decode()))
            return token_response()

        access_token = tokens_answering(account, handler).access_token()

        form = sent_forms[0]
        claims = jwt.decode(form["assertion"][0], options={"verify_signature": False})
        assert access_token == "token-1"
        assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
        assert claims["iss"] == account.client_email
        assert claims["scope"] == SHEETS_SCOPE
        assert claims["aud"] == TOKEN_URI

    def test_reuses_the_token_while_it_is_valid(self, account: ServiceAccount) -> None:
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return token_response(f"token-{request_count}")

        tokens = tokens_answering(account, handler)

        assert tokens.access_token() == tokens.access_token() == "token-1"
        assert request_count == 1

    def test_fetches_a_new_token_shortly_before_expiry(self, account: ServiceAccount) -> None:
        current_time = NOW
        request_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return token_response(f"token-{request_count}", expires_in=3600)

        tokens = tokens_answering(account, handler, clock=lambda: current_time)
        tokens.access_token()
        current_time = NOW + timedelta(minutes=59, seconds=30)

        assert tokens.access_token() == "token-2"

    def test_reports_a_refused_token_request(self, account: ServiceAccount) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "invalid_grant"})

        with pytest.raises(GoogleAuthError, match="invalid_grant"):
            tokens_answering(account, handler).access_token()
