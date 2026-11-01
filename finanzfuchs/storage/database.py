"""Opening the database and keeping its schema current.

One connection per unit of work (a request, a CLI command): SQLite opens fast, and it keeps
threads of the web server from sharing a connection.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from finanzfuchs.plan import default_kind

SCHEMA_VERSION = 2

INITIAL_SCHEMA = """
CREATE TABLE plan_lines (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    rhythm TEXT NOT NULL,
    pot TEXT NOT NULL DEFAULT '',
    valid_from TEXT NOT NULL,
    valid_until TEXT
);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position REAL NOT NULL,
    plan_line_id TEXT NOT NULL REFERENCES plan_lines(id),
    counterparty_contains TEXT NOT NULL DEFAULT '',
    purpose_contains TEXT NOT NULL DEFAULT '',
    counterparty_iban TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    account TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    imported_by TEXT NOT NULL,
    added_count INTEGER NOT NULL,
    skipped_count INTEGER NOT NULL
);

CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    counterparty_name TEXT NOT NULL,
    counterparty_iban TEXT NOT NULL,
    purpose TEXT NOT NULL,
    plan_line_id TEXT REFERENCES plan_lines(id),
    source TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    import_id INTEGER REFERENCES imports(id)
);
CREATE INDEX transactions_by_date ON transactions(booking_date);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    name TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE login_requests (
    state TEXT PRIMARY KEY,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


class DatabaseError(RuntimeError):
    """The database file is from a newer version of Finanzfuchs or unusable."""


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            _migrate(connection, self._path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Commits when the block succeeds, rolls back when it raises."""
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def _migrate(connection: sqlite3.Connection, path: Path) -> None:
    """A new database gets the first schema, then every database runs the steps it lacks."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise DatabaseError(
            f"{path} has schema version {version}; this Finanzfuchs knows only {SCHEMA_VERSION}"
        )
    if version == 0:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(INITIAL_SCHEMA)
        version = 1
    for target_version in range(version + 1, SCHEMA_VERSION + 1):
        MIGRATIONS[target_version](connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _add_plan_line_kind(connection: sqlite3.Connection) -> None:
    """Version 2: fixed or variable, guessed for the existing lines."""
    connection.execute("ALTER TABLE plan_lines ADD COLUMN kind TEXT NOT NULL DEFAULT 'variabel'")
    rows = connection.execute("SELECT id, type, category, pot FROM plan_lines").fetchall()
    connection.executemany(
        "UPDATE plan_lines SET kind = ? WHERE id = ?",
        [(default_kind(row["type"], row["category"], row["pot"]), row["id"]) for row in rows],
    )


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {2: _add_plan_line_kind}
