import sqlite3
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from finanzfuchs.plan import PlanLine
from finanzfuchs.storage.database import Database

JOINT_ACCOUNT = "DE00111111110000000001"
EXPORT_HEADER = (
    f'"Girokonto";"{JOINT_ACCOUNT}"\n'
    '"Zeitraum:";"01.01.2026 - 31.10.2026"\n'
    '"Kontostand vom 31.10.2026:";"1.000,00 €"\n'
    '""\n'
    '"Buchungsdatum";"Wertstellung";"Status";"Zahlungspflichtige*r";"Zahlungsempfänger*in";'
    '"Verwendungszweck";"Umsatztyp";"IBAN";"Betrag (€)";"Gläubiger-ID";"Mandatsreferenz";'
    '"Kundenreferenz"\n'
)


def export_row(day: str, payee: str, amount: str, status: str = "Gebucht") -> str:
    """A payment row of a DKB export; `day` like `30.10.26`, `amount` like `-20,30`."""
    return (
        f'"{day}";"{day}";"{status}";"ISSUER";"{payee}";"VISA Debitkartenumsatz";"Ausgang";'
        f'"DE96120300009005290904";"{amount}";"";"";"{payee}-{day}"\n'
    )


def dkb_export(*rows: str) -> str:
    return "﻿" + EXPORT_HEADER + "".join(rows)


def plan_line(
    plan_line_id: str, category: str = "Täglicher Bedarf", amount: str = "800"
) -> PlanLine:
    return PlanLine(
        plan_line_id=plan_line_id,
        line_type="Ausgabe",
        category=category,
        description=plan_line_id.capitalize(),
        amount=Decimal(amount),
        rhythm="Monat",
        pot="",
        valid_from=date(2026, 1, 1),
        valid_until=None,
    )


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "finanzfuchs.sqlite3")
    database.initialize()
    return database


@pytest.fixture
def connection(database: Database) -> Iterator[sqlite3.Connection]:
    with database.connect() as connection:
        yield connection
