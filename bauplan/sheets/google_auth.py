"""Access tokens for a Google service account (OAuth 2.0 JWT bearer flow).

Written against the token endpoint directly: two requests do not justify the Google client
libraries, and pyjwt is already needed for Enable Banking.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
ASSERTION_LIFETIME = timedelta(hours=1)
# Renew a little early so a token never expires in the middle of a run.
EXPIRY_MARGIN = timedelta(minutes=1)


class GoogleAuthError(RuntimeError):
    """The service account key is unusable or Google refused it."""


@dataclass(frozen=True)
class ServiceAccount:
    client_email: str
    private_key_pem: str
    token_uri: str

    @classmethod
    def from_key_file(cls, path: Path) -> "ServiceAccount":
        try:
            key = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            raise GoogleAuthError(f"Cannot read the service account key {path}: {error}") from error
        if key.get("type") != "service_account":
            raise GoogleAuthError(f"{path} is not a service account key (type {key.get('type')!r})")
        return cls(
            client_email=key["client_email"],
            private_key_pem=key["private_key"],
            token_uri=key["token_uri"],
        )


class ServiceAccountTokens:
    def __init__(
        self,
        account: ServiceAccount,
        http_client: httpx.Client,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._account = account
        self._http_client = http_client
        self._clock = clock
        self._access_token: str | None = None
        self._renew_at = datetime.min.replace(tzinfo=UTC)

    def access_token(self) -> str:
        now = self._clock()
        if self._access_token is None or now >= self._renew_at:
            self._access_token = self._fetch_token(now)
        return self._access_token

    def _fetch_token(self, now: datetime) -> str:
        response = self._http_client.post(
            self._account.token_uri,
            data={"grant_type": JWT_BEARER_GRANT, "assertion": self._build_assertion(now)},
        )
        if not response.is_success:
            raise GoogleAuthError(
                f"Google refused a token for {self._account.client_email}: "
                f"{response.status_code} {response.text}"
            )
        body = response.json()
        self._renew_at = now + timedelta(seconds=body["expires_in"]) - EXPIRY_MARGIN
        return body["access_token"]

    def _build_assertion(self, now: datetime) -> str:
        issued_at = int(now.timestamp())
        claims = {
            "iss": self._account.client_email,
            "scope": SHEETS_SCOPE,
            "aud": self._account.token_uri,
            "iat": issued_at,
            "exp": issued_at + int(ASSERTION_LIFETIME.total_seconds()),
        }
        return jwt.encode(claims, self._account.private_key_pem, algorithm="RS256")
