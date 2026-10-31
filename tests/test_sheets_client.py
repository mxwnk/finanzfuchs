import json

import httpx
import pytest

from bauplan.sheets.client import API_BASE_URL, SheetsClient, SheetsError

SPREADSHEET_ID = "sheet-123"


class FakeTokens:
    def access_token(self) -> str:
        return "token-1"


def client_answering(handler) -> SheetsClient:
    http_client = httpx.Client(base_url=API_BASE_URL, transport=httpx.MockTransport(handler))
    return SheetsClient(SPREADSHEET_ID, FakeTokens(), http_client)


def test_lists_the_tab_titles_and_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token-1"
        assert request.url.path == f"/v4/spreadsheets/{SPREADSHEET_ID}"
        sheets = [{"properties": {"title": "Plan", "sheetId": 7}}]
        return httpx.Response(200, json={"sheets": sheets})

    tabs = client_answering(handler).tab_ids()

    assert tabs == {"Plan": 7}


def test_reads_raw_values_with_dates_as_numbers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["valueRenderOption"] == "UNFORMATTED_VALUE"
        assert request.url.params["dateTimeRenderOption"] == "SERIAL_NUMBER"
        return httpx.Response(200, json={"values": [["t1", 46083]]})

    values = client_answering(handler).read_values("Buchungen!A2:H")

    assert values == [["t1", 46083]]


def test_an_empty_range_reads_as_no_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"range": "Buchungen!A2:H"})

    assert client_answering(handler).read_values("Buchungen!A2:H") == []


def test_quotes_tab_names_with_special_characters_in_the_path() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.raw_path.decode())
        return httpx.Response(200, json={})

    client_answering(handler).write_values("'Fixkosten-Topf'!A1", [["x"]], as_formulas=True)

    assert "%27Fixkosten-Topf%27%21A1" in requested_paths[0]


def test_writes_bank_data_raw_and_own_formulas_as_entered() -> None:
    input_options: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        input_options.append(request.url.params["valueInputOption"])
        return httpx.Response(200, json={})

    client = client_answering(handler)
    client.write_values("Plan!A2", [["gez"]], as_formulas=False)
    client.write_values("Plan!J1", [["=1"]], as_formulas=True)

    assert input_options == ["RAW", "USER_ENTERED"]


def test_appends_rows_raw_as_new_rows() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    client_answering(handler).append_rows("Buchungen!A:H", [["t1", 46083]])

    request = sent[0]
    assert request.url.path.endswith(":append")
    assert request.url.params["valueInputOption"] == "RAW"
    assert request.url.params["insertDataOption"] == "INSERT_ROWS"
    assert json.loads(request.content) == {"values": [["t1", 46083]]}


def test_writes_several_ranges_in_one_request() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={})

    client_answering(handler).write_ranges({"Buchungen!F3:H3": [["sky-abo", "Regel 7", ""]]})

    assert bodies[0] == {
        "valueInputOption": "RAW",
        "data": [{"range": "Buchungen!F3:H3", "values": [["sky-abo", "Regel 7", ""]]}],
    }


def test_skips_the_request_when_there_is_nothing_to_write() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    client = client_answering(handler)
    client.write_ranges({})
    client.append_rows("Buchungen!A:H", [])
    client.batch_update([])


def test_reports_status_and_answer_of_a_refused_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"message": "The caller does not have permission"}}
        )

    with pytest.raises(SheetsError, match="403.*permission"):
        client_answering(handler).tab_ids()
