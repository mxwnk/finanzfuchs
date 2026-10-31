"""Plan lines in the database, in the order the plan was written."""

import sqlite3
from datetime import date

from finanzfuchs.plan import PlanLine
from finanzfuchs.storage.money import from_cents, to_cents


class PlanStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def lines(self) -> list[PlanLine]:
        rows = self._connection.execute("SELECT * FROM plan_lines ORDER BY position")
        return [_to_plan_line(row) for row in rows]

    def get(self, plan_line_id: str) -> PlanLine | None:
        row = self._connection.execute(
            "SELECT * FROM plan_lines WHERE id = ?", (plan_line_id,)
        ).fetchone()
        return _to_plan_line(row) if row else None

    def is_empty(self) -> bool:
        return self._connection.execute("SELECT COUNT(*) FROM plan_lines").fetchone()[0] == 0

    def add(self, line: PlanLine) -> None:
        position = self._connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM plan_lines"
        ).fetchone()[0]
        self._connection.execute(
            """INSERT INTO plan_lines (id, position, type, category, description, amount_cents,
                   rhythm, pot, valid_from, valid_until)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (line.plan_line_id, position, *_editable_values(line)),
        )

    def update(self, line: PlanLine) -> None:
        self._connection.execute(
            """UPDATE plan_lines SET type = ?, category = ?, description = ?, amount_cents = ?,
                   rhythm = ?, pot = ?, valid_from = ?, valid_until = ?
               WHERE id = ?""",
            (*_editable_values(line), line.plan_line_id),
        )


def _editable_values(line: PlanLine) -> tuple[object, ...]:
    return (
        line.line_type,
        line.category,
        line.description,
        to_cents(line.amount),
        line.rhythm,
        line.pot,
        line.valid_from.isoformat(),
        line.valid_until.isoformat() if line.valid_until else None,
    )


def _to_plan_line(row: sqlite3.Row) -> PlanLine:
    return PlanLine(
        plan_line_id=row["id"],
        line_type=row["type"],
        category=row["category"],
        description=row["description"],
        amount=from_cents(row["amount_cents"]),
        rhythm=row["rhythm"],
        pot=row["pot"],
        valid_from=date.fromisoformat(row["valid_from"]),
        valid_until=date.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
    )
