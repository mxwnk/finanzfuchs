"""The pure parts of talking to Enable Banking: signing requests and the bank approval."""

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt

TOKEN_ISSUER = "enablebanking.com"
TOKEN_AUDIENCE = "api.enablebanking.com"
TOKEN_ALGORITHM = "RS256"
# Enable Banking rejects tokens living longer than a day; one hour covers any single run.
TOKEN_LIFETIME = timedelta(hours=1)
# Enable Banking's default since October 2025; the bank may allow less.
DEFAULT_CONSENT_VALIDITY = timedelta(days=180)


class AuthorizationRedirectError(ValueError):
    """The address the bank redirected to does not carry a usable approval."""


def build_application_token(application_id: str, private_key_pem: str, now: datetime) -> str:
    issued_at = int(now.timestamp())
    claims = {
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": issued_at,
        "exp": issued_at + int(TOKEN_LIFETIME.total_seconds()),
    }
    return jwt.encode(
        claims, private_key_pem, algorithm=TOKEN_ALGORITHM, headers={"kid": application_id}
    )


def choose_consent_end(now: datetime, bank_maximum_seconds: int | None) -> datetime:
    if bank_maximum_seconds is None:
        return now + DEFAULT_CONSENT_VALIDITY
    bank_maximum = timedelta(seconds=bank_maximum_seconds)
    return now + min(DEFAULT_CONSENT_VALIDITY, bank_maximum)


def read_authorization_code(redirect_url: str, expected_state: str) -> str:
    parameters = parse_qs(urlparse(redirect_url.strip()).query)
    _ensure_same_authorization(parameters, expected_state)
    _ensure_no_bank_error(parameters)
    codes = parameters.get("code")
    if not codes:
        raise AuthorizationRedirectError(f"No code in the redirect address: {redirect_url}")
    return codes[0]


def _ensure_same_authorization(parameters: dict[str, list[str]], expected_state: str) -> None:
    received_state = parameters.get("state", [""])[0]
    if received_state != expected_state:
        raise AuthorizationRedirectError(
            f"The redirect belongs to another approval (state {received_state!r}, "
            f"expected {expected_state!r}); start `connect` again"
        )


def _ensure_no_bank_error(parameters: dict[str, list[str]]) -> None:
    if "error" not in parameters:
        return
    error = parameters["error"][0]
    description = parameters.get("error_description", [""])[0]
    raise AuthorizationRedirectError(f"The bank approval failed: {error} ({description})")
