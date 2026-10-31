"""One-time takeover of the files from before the app: plan, rules and the DKB exports."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from finanzfuchs.assignment.rules import load_rules
from finanzfuchs.importing import ImportSummary, import_dkb_export
from finanzfuchs.plan import load_plan
from finanzfuchs.storage.plan_store import PlanStore
from finanzfuchs.storage.rule_store import RuleStore

SEED_USER = "Übernahme"


class SeedError(RuntimeError):
    """The database already holds a plan; seeding would mix two plans."""


@dataclass(frozen=True)
class SeedSummary:
    plan_line_count: int
    rule_count: int
    imports: list[ImportSummary]


def seed_from_files(
    connection: sqlite3.Connection,
    plan_file: Path,
    rules_file: Path,
    export_files: list[Path],
    now: datetime,
) -> SeedSummary:
    plan_store = PlanStore(connection)
    if not plan_store.is_empty():
        raise SeedError("The database already has a plan; seeding works only on an empty one")
    plan = load_plan(plan_file)
    for line in plan:
        plan_store.add(line)
    rules = load_rules(rules_file)
    rule_store = RuleStore(connection)
    for rule in rules:
        rule_store.append(rule)
    imports = [
        import_dkb_export(
            connection, path.read_text(encoding="utf-8-sig"), path.name, SEED_USER, now
        )
        for path in sorted(export_files)
    ]
    return SeedSummary(plan_line_count=len(plan), rule_count=len(rules), imports=imports)
