"""Login sessions and the logins still waiting for Pocket ID's answer.

Only a hash of the session token is stored: a copy of the database must not let anyone in.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SessionUser:
    subject: str
    name: str


@dataclass(frozen=True)
class PendingLogin:
    nonce: str
    code_verifier: str


class SessionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create_session(self, token: str, user: SessionUser, expires_at: datetime) -> None:
        self._connection.execute(
            "INSERT INTO sessions (token_hash, subject, name, expires_at) VALUES (?, ?, ?, ?)",
            (_hash(token), user.subject, user.name, expires_at.isoformat()),
        )

    def find_user(self, token: str, now: datetime) -> SessionUser | None:
        row = self._connection.execute(
            "SELECT subject, name FROM sessions WHERE token_hash = ? AND expires_at > ?",
            (_hash(token), now.isoformat()),
        ).fetchone()
        return SessionUser(row["subject"], row["name"]) if row else None

    def delete_session(self, token: str) -> None:
        self._connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))

    def save_login(self, state: str, login: PendingLogin, expires_at: datetime) -> None:
        self._connection.execute(
            """INSERT INTO login_requests (state, nonce, code_verifier, expires_at)
               VALUES (?, ?, ?, ?)""",
            (state, login.nonce, login.code_verifier, expires_at.isoformat()),
        )

    def take_login(self, state: str, now: datetime) -> PendingLogin | None:
        """A login request can be answered once; afterwards it is gone."""
        row = self._connection.execute(
            "SELECT nonce, code_verifier, expires_at FROM login_requests WHERE state = ?", (state,)
        ).fetchone()
        self._connection.execute("DELETE FROM login_requests WHERE state = ?", (state,))
        if row is None or row["expires_at"] <= now.isoformat():
            return None
        return PendingLogin(row["nonce"], row["code_verifier"])

    def forget_expired(self, now: datetime) -> None:
        moment = now.isoformat()
        self._connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (moment,))
        self._connection.execute("DELETE FROM login_requests WHERE expires_at <= ?", (moment,))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
