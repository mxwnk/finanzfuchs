"""Login with Pocket ID and the session cookie that follows it.

Only members of the family group get in. There is no way around the login anywhere in the code;
tests use a fake provider.
"""

import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from finanzfuchs.storage.database import Database
from finanzfuchs.storage.session_store import PendingLogin, SessionStore, SessionUser
from finanzfuchs.web.oidc import LoginRequest, OidcError, VerifiedLogin

LOGIN_REQUEST_LIFETIME = timedelta(minutes=10)
SESSION_LIFETIME = timedelta(days=30)
TOKEN_BYTES = 32

Clock = Callable[[], datetime]
logger = logging.getLogger(__name__)


class LoginRejectedError(RuntimeError):
    """A login step cannot go on; the message is for the log, not for the page."""


class IdentityProvider(Protocol):
    def start_login(self) -> LoginRequest: ...

    def finish_login(self, code: str, code_verifier: str, nonce: str) -> VerifiedLogin: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class LoginFlow:
    def __init__(
        self,
        provider: IdentityProvider,
        database: Database,
        allowed_group: str,
        now: Clock = utc_now,
    ) -> None:
        self._provider = provider
        self._database = database
        self._allowed_group = allowed_group
        self._now = now

    def start(self) -> str:
        """The address of the provider's login page."""
        request = self._provider.start_login()
        with self._database.connect() as connection:
            store = SessionStore(connection)
            store.forget_expired(self._now())
            store.save_login(
                request.state,
                PendingLogin(request.nonce, request.code_verifier),
                self._now() + LOGIN_REQUEST_LIFETIME,
            )
        return request.authorization_url

    def finish(self, state: str, code: str) -> str:
        """Verifies the provider's answer and returns a new session token."""
        with self._database.connect() as connection:
            pending = SessionStore(connection).take_login(state, self._now())
        if pending is None:
            raise LoginRejectedError("Unknown, used or expired login state")
        login = self._verified(code, pending)
        if self._allowed_group not in login.groups:
            raise LoginRejectedError(f"{login.subject} is not in group {self._allowed_group!r}")
        return self._new_session(SessionUser(login.subject, login.name or login.subject))

    def user_for(self, token: str | None) -> SessionUser | None:
        if not token:
            return None
        with self._database.connect() as connection:
            return SessionStore(connection).find_user(token, self._now())

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._database.connect() as connection:
            SessionStore(connection).delete_session(token)

    def _verified(self, code: str, pending: PendingLogin) -> VerifiedLogin:
        try:
            return self._provider.finish_login(code, pending.code_verifier, pending.nonce)
        except OidcError as error:
            raise LoginRejectedError(f"Pocket ID login failed: {error}") from error

    def _new_session(self, user: SessionUser) -> str:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        with self._database.connect() as connection:
            SessionStore(connection).create_session(token, user, self._now() + SESSION_LIFETIME)
        logger.info("Login of %s", user.name)
        return token
