"""Assignment rules in the order they are tried; rules made in the app go to the top."""

import sqlite3
from dataclasses import dataclass

from finanzfuchs.assignment.rules import AssignmentRule

FIELDS = ("plan_line_id", "counterparty_contains", "purpose_contains", "counterparty_iban",
          "direction", "note")  # fmt: skip


@dataclass(frozen=True)
class StoredRule:
    rule_id: int
    rule: AssignmentRule


class RuleStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list(self) -> list[StoredRule]:
        rows = self._connection.execute(
            f"SELECT id, {', '.join(FIELDS)} FROM rules ORDER BY position"
        )
        return [
            StoredRule(row["id"], AssignmentRule(**{f: row[f] for f in FIELDS})) for row in rows
        ]

    def append(self, rule: AssignmentRule) -> int:
        return self._insert(rule, "SELECT COALESCE(MAX(position), 0) + 1 FROM rules")

    def add_at_top(self, rule: AssignmentRule) -> int:
        """A rule made for one counterparty is more specific than the general ones below."""
        return self._insert(rule, "SELECT COALESCE(MIN(position), 0) - 1 FROM rules")

    def _insert(self, rule: AssignmentRule, position_query: str) -> int:
        position = self._connection.execute(position_query).fetchone()[0]
        cursor = self._connection.execute(
            f"INSERT INTO rules (position, {', '.join(FIELDS)}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (position, *(getattr(rule, field) for field in FIELDS)),
        )
        return int(cursor.lastrowid or 0)
