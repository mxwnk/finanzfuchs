"""OpenID Connect against Pocket ID: authorization code flow with PKCE and a verified ID token.

Taken from the Fuxbau household app. Only the server talks to the token endpoint; the browser
never sees a provider token, only the session cookie Finanzfuchs sets afterwards.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import jwt

DISCOVERY_PATH = "/.well-known/openid-configuration"
# `groups` makes Pocket ID put the user's group names into the ID token.
SCOPES = "openid profile email groups"
ALLOWED_ALGORITHMS = ("RS256",)
REQUEST_TIMEOUT_SECONDS = 10
RANDOM_BYTES = 32
# Pocket ID and the backend clocks may drift a little; tokens are only checked once at login.
CLOCK_LEEWAY_SECONDS = 30


class OidcError(RuntimeError):
    """Raised when the provider answers unexpectedly or a token fails verification."""


@dataclass(frozen=True)
class OidcClientConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class LoginRequest:
    """What the backend keeps while the user is at the provider."""

    state: str
    nonce: str
    code_verifier: str
    authorization_url: str


@dataclass(frozen=True)
class VerifiedLogin:
    subject: str
    name: str | None
    groups: frozenset[str]


class Http(Protocol):
    def get(self, url: str) -> httpx.Response: ...
    def post(self, url: str, data: dict[str, str], auth: tuple[str, str]) -> httpx.Response: ...


class OidcClient:
    def __init__(self, config: OidcClientConfig, http: Http | None = None):
        self._config = config
        self._http = http or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    def start_login(self) -> LoginRequest:
        state, nonce, verifier = (_random_text() for _ in range(3))
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._config.client_id,
                "redirect_uri": self._config.redirect_uri,
                "scope": SCOPES,
                "state": state,
                "nonce": nonce,
                "code_challenge": _code_challenge(verifier),
                "code_challenge_method": "S256",
            }
        )
        url = f"{self._discovery['authorization_endpoint']}?{query}"
        return LoginRequest(state, nonce, verifier, url)

    def finish_login(self, code: str, code_verifier: str, nonce: str) -> VerifiedLogin:
        id_token = self._exchange(code, code_verifier)
        claims = self._verified_claims(id_token)
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("ID token nonce does not match the login request")
        return VerifiedLogin(
            subject=str(claims["sub"]),
            name=claims.get("name"),
            groups=_groups_from(claims),
        )

    def _exchange(self, code: str, code_verifier: str) -> str:
        response = self._http.post(
            self._discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._config.redirect_uri,
                "code_verifier": code_verifier,
            },
            auth=(self._config.client_id, self._config.client_secret),
        )
        if response.status_code != httpx.codes.OK:
            raise OidcError(
                f"Token endpoint answered {response.status_code}: {response.text[:200]}"
            )
        id_token = response.json().get("id_token")
        if not id_token:
            raise OidcError("Token endpoint answered without an id_token")
        return id_token

    def _verified_claims(self, id_token: str) -> dict[str, Any]:
        try:
            key = self._signing_key(jwt.get_unverified_header(id_token).get("kid"))
            return jwt.decode(
                id_token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self._config.client_id,
                issuer=self._config.issuer,
                leeway=CLOCK_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "nonce"]},
            )
        except jwt.PyJWTError as error:
            raise OidcError(f"ID token rejected: {error}") from error

    def _signing_key(self, key_id: str | None) -> Any:
        keys = self._json(self._discovery["jwks_uri"])["keys"]
        match = next((key for key in keys if key.get("kid") == key_id), None)
        if match is None:
            raise OidcError(f"No signing key {key_id!r} at the provider")
        return jwt.PyJWK(match).key

    @cached_property
    def _discovery(self) -> dict[str, Any]:
        discovery = self._json(self._config.issuer.rstrip("/") + DISCOVERY_PATH)
        announced = discovery.get("issuer")
        if announced != self._config.issuer:
            raise OidcError(f"Provider says issuer {announced!r}, expected {self._config.issuer!r}")
        return discovery

    def _json(self, url: str) -> dict[str, Any]:
        response = self._http.get(url)
        if response.status_code != httpx.codes.OK:
            raise OidcError(f"{url} answered {response.status_code}")
        return response.json()


def _groups_from(claims: dict[str, Any]) -> frozenset[str]:
    groups = claims.get("groups")
    if not isinstance(groups, list):
        return frozenset()
    return frozenset(str(group) for group in groups)


def _random_text() -> str:
    return secrets.token_urlsafe(RANDOM_BYTES)


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
