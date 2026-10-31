from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from bauplan.banking.authorization import (
    DEFAULT_CONSENT_VALIDITY,
    AuthorizationRedirectError,
    build_application_token,
    choose_consent_end,
    read_authorization_code,
)

APPLICATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
NOW = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="module")
def public_key_pem(private_key_pem: str) -> str:
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    return (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


class TestApplicationToken:
    def test_names_the_application_in_the_header(self, private_key_pem: str) -> None:
        token = build_application_token(APPLICATION_ID, private_key_pem, NOW)

        header = jwt.get_unverified_header(token)

        assert header["kid"] == APPLICATION_ID
        assert header["alg"] == "RS256"

    def test_is_signed_for_the_enable_banking_api(
        self, private_key_pem: str, public_key_pem: str
    ) -> None:
        token = build_application_token(APPLICATION_ID, private_key_pem, NOW)

        claims = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            audience="api.enablebanking.com",
            issuer="enablebanking.com",
            options={"verify_exp": False, "verify_iat": False},
        )

        assert claims["iat"] == int(NOW.timestamp())

    def test_expires_within_the_allowed_day(self, private_key_pem: str) -> None:
        token = build_application_token(APPLICATION_ID, private_key_pem, NOW)

        claims = jwt.decode(token, options={"verify_signature": False})

        assert 0 < claims["exp"] - claims["iat"] <= 86_400


class TestConsentEnd:
    def test_uses_the_default_validity_when_the_bank_allows_more(self) -> None:
        bank_maximum_seconds = int(timedelta(days=365).total_seconds())

        consent_end = choose_consent_end(NOW, bank_maximum_seconds)

        assert consent_end == NOW + DEFAULT_CONSENT_VALIDITY

    def test_respects_a_shorter_bank_maximum(self) -> None:
        ninety_days = timedelta(days=90)

        consent_end = choose_consent_end(NOW, int(ninety_days.total_seconds()))

        assert consent_end == NOW + ninety_days

    def test_uses_the_default_validity_when_the_bank_states_no_maximum(self) -> None:
        consent_end = choose_consent_end(NOW, None)

        assert consent_end == NOW + DEFAULT_CONSENT_VALIDITY


class TestAuthorizationCode:
    def test_reads_the_code_from_the_redirect_url(self) -> None:
        redirect = "https://fuxbau.org/bauplan/callback?state=state-1&code=code-123"

        code = read_authorization_code(redirect, expected_state="state-1")

        assert code == "code-123"

    def test_rejects_a_redirect_from_another_authorization(self) -> None:
        redirect = "https://fuxbau.org/bauplan/callback?state=other&code=code-123"

        with pytest.raises(AuthorizationRedirectError, match="state"):
            read_authorization_code(redirect, expected_state="state-1")

    def test_reports_the_error_the_bank_sent_back(self) -> None:
        redirect = (
            "https://fuxbau.org/bauplan/callback?state=state-1"
            "&error=access_denied&error_description=User+cancelled"
        )

        with pytest.raises(AuthorizationRedirectError, match="User cancelled"):
            read_authorization_code(redirect, expected_state="state-1")

    def test_rejects_a_redirect_without_code(self) -> None:
        redirect = "https://fuxbau.org/bauplan/callback?state=state-1"

        with pytest.raises(AuthorizationRedirectError, match="code"):
            read_authorization_code(redirect, expected_state="state-1")
