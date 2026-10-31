import json
import re
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from conftest import plan_line
from openpyxl import load_workbook

from finanzfuchs.banking.transactions import BankTransaction
from finanzfuchs.dashboard.dataset import build_dataset
from finanzfuchs.dashboard.render import DATA_PLACEHOLDER, render_dashboard
from finanzfuchs.export import build_workbook
from finanzfuchs.ledger import AssignmentSource, LedgerEntry
from finanzfuchs.plan import PlanLine

GENERATED_AT = datetime(2026, 11, 1, 8, 30)
GEZ = PlanLine("gez", "Ausgabe", "Wohnen", "GEZ", Decimal("220.32"), "Jahr", "Fixkosten",
               date(2026, 1, 1), None)  # fmt: skip


def entry(counterparty: str = "Rundfunk", line: str | None = "gez", note: str = "") -> LedgerEntry:
    transaction = BankTransaction("t1", "DE01", date(2026, 1, 5), Decimal("-220.32"),
                                  counterparty, "DE28", "Beitrag 2026", True)  # fmt: skip
    source = AssignmentSource.RULE if line else AssignmentSource.OPEN
    return LedgerEntry(transaction, line, source, note)


class TestDataset:
    def test_turns_yearly_amounts_into_monthly_ones(self) -> None:
        [gez] = build_dataset([GEZ], [], GENERATED_AT)["plan"]

        assert gez["monthly"] == 18.36
        assert (gez["validFrom"], gez["validUntil"]) == ("2026-01-01", None)

    def test_carries_each_transaction_with_its_assignment(self) -> None:
        [transaction] = build_dataset([GEZ], [entry(note="ZWEIFEL: ?")], GENERATED_AT)[
            "transactions"
        ]

        assert transaction == {
            "id": "t1", "date": "2026-01-05", "amount": -220.32, "counterparty": "Rundfunk",
            "purpose": "Beitrag 2026", "line": "gez", "source": "rule", "note": "ZWEIFEL: ?",
        }  # fmt: skip

    def test_an_open_transaction_has_an_empty_line(self) -> None:
        [transaction] = build_dataset([GEZ], [entry(line=None)], GENERATED_AT)["transactions"]

        assert transaction["line"] == ""


class TestRender:
    def test_embeds_the_data_into_the_page(self) -> None:
        html = render_dashboard(build_dataset([GEZ], [entry()], GENERATED_AT))

        embedded = re.search(r"window\.BAUPLAN_DATA = (.*?);\n", html)
        assert embedded is not None
        assert json.loads(embedded.group(1))["generatedAt"] == "2026-11-01T08:30:00"
        assert DATA_PLACEHOLDER not in html

    def test_loads_nothing_from_the_internet(self) -> None:
        html = render_dashboard(build_dataset([GEZ], [], GENERATED_AT))

        assert not re.search(r"<(script|link)[^>]+(src|href)=\"https?://", html)

    def test_bank_text_cannot_close_the_script_tag(self) -> None:
        hostile = entry(counterparty="</script><script>alert(1)</script>")

        html = render_dashboard(build_dataset([GEZ], [hostile], GENERATED_AT))

        assert "</script><script>alert(1)" not in html


class TestExport:
    def test_writes_transactions_and_plan_sheets(self) -> None:
        content = build_workbook([GEZ, plan_line("lebensmittel")], [entry(), entry(line=None)])

        workbook = load_workbook(BytesIO(content))

        assert workbook.sheetnames == ["Buchungen", "Plan"]
        rows = list(workbook["Buchungen"].iter_rows(min_row=2, values_only=True))
        assert rows[0][1:7] == (-220.32, "Rundfunk", "Beitrag 2026", "GEZ", "Wohnen", "Regel")
        assert rows[1][6] == "offen"
        assert workbook["Plan"]["G2"].value == 18.36
