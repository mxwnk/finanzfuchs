import json
import re
from datetime import datetime

import pytest

from bauplan.dashboard.dataset import DashboardDataError, build_dataset
from bauplan.dashboard.render import DATA_PLACEHOLDER, render_dashboard

GENERATED_AT = datetime(2026, 11, 1, 8, 30)
PLAN_ROWS = [
    ["gez", "Ausgabe", "Wohnen", "GEZ", 220.32, "Jahr", "Fixkosten", 46023, ""],
    ["elterngeld", "Einnahme", "Einnahmen", "Elterngeld", 150, "Monat", "", 46023, 46387],
]
TRANSACTION_ROWS = [
    ["t1", 46027, -220.32, "Rundfunk", "Beitrag 2026", "gez", "Regel 3", ""],
    ["t2", 46030, 150, "Bundeskasse", "ELTG", "elterngeld", "", "ZWEIFEL: wirklich?"],
    ["t3", 46031, -9.99, "Unbekannt", "", "", "", ""],
]


def dataset() -> dict:
    return build_dataset(PLAN_ROWS, TRANSACTION_ROWS, GENERATED_AT)


class TestPlan:
    def test_turns_yearly_amounts_into_monthly_ones(self) -> None:
        [gez, _] = dataset()["plan"]

        assert gez["monthly"] == pytest.approx(18.36)
        assert gez["category"] == "Wohnen"
        assert gez["pot"] == "Fixkosten"

    def test_reads_validity_dates_from_sheet_serials(self) -> None:
        [gez, elterngeld] = dataset()["plan"]

        assert gez["validFrom"] == "2026-01-01"
        assert gez["validUntil"] is None
        assert elterngeld["validUntil"] == "2026-12-31"

    def test_skips_empty_plan_rows(self) -> None:
        data = build_dataset([*PLAN_ROWS, [], [""]], TRANSACTION_ROWS, GENERATED_AT)

        assert len(data["plan"]) == 2

    def test_names_the_row_of_an_unreadable_plan_line(self) -> None:
        broken = [["gez", "Ausgabe", "Wohnen", "GEZ", "viel", "Jahr", "", 46023, ""]]

        with pytest.raises(DashboardDataError, match="Plan row 2"):
            build_dataset(broken, [], GENERATED_AT)


class TestTransactions:
    def test_keeps_date_amount_counterparty_and_assignment(self) -> None:
        first = dataset()["transactions"][0]

        assert first == {
            "id": "t1",
            "date": "2026-01-05",
            "amount": -220.32,
            "counterparty": "Rundfunk",
            "purpose": "Beitrag 2026",
            "line": "gez",
            "source": "Regel 3",
            "note": "",
        }

    def test_keeps_open_transactions_without_a_line(self) -> None:
        assert dataset()["transactions"][2]["line"] == ""

    def test_tolerates_short_rows_for_empty_trailing_cells(self) -> None:
        data = build_dataset(PLAN_ROWS, [["t9", 46031, -5]], GENERATED_AT)

        assert data["transactions"][0]["note"] == ""

    def test_names_the_row_of_an_unreadable_transaction(self) -> None:
        with pytest.raises(DashboardDataError, match="Buchungen row 2"):
            build_dataset(PLAN_ROWS, [["t1", "gestern", -5]], GENERATED_AT)


class TestRender:
    def test_embeds_the_data_into_the_page(self) -> None:
        html = render_dashboard(dataset())

        embedded = re.search(r"window\.BAUPLAN_DATA = (.*?);\n", html)
        assert embedded is not None
        assert json.loads(embedded.group(1))["generatedAt"] == "2026-11-01T08:30:00"
        assert DATA_PLACEHOLDER not in html

    def test_loads_nothing_from_the_internet(self) -> None:
        html = render_dashboard(dataset())

        assert "echarts" in html.lower()
        assert not re.search(r"<(script|link)[^>]+(src|href)=\"https?://", html)

    def test_bank_text_cannot_close_the_script_tag(self) -> None:
        hostile = build_dataset(
            PLAN_ROWS,
            [["t1", 46027, -1, "</script><script>alert(1)</script>", "", "", "", ""]],
            GENERATED_AT,
        )

        html = render_dashboard(hostile)

        assert "</script><script>alert(1)" not in html
