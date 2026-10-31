"""HTTP client for the few Google Sheets API calls Bauplan needs."""

from typing import Any, Protocol
from urllib.parse import quote

import httpx

API_BASE_URL = "https://sheets.googleapis.com"
REQUEST_TIMEOUT_SECONDS = 30.0
RAW_INPUT = "RAW"
"""Values are stored as given: bank text starting with `=` never becomes a formula."""
FORMULA_INPUT = "USER_ENTERED"

SheetValue = str | int | float
Rows = list[list[SheetValue]]


class SheetsError(RuntimeError):
    """Google refused a Sheets request."""


class AccessTokens(Protocol):
    def access_token(self) -> str: ...


class SheetsClient:
    def __init__(
        self, spreadsheet_id: str, tokens: AccessTokens, http_client: httpx.Client
    ) -> None:
        self._base_path = f"/v4/spreadsheets/{spreadsheet_id}"
        self._tokens = tokens
        self._http_client = http_client

    @classmethod
    def connect(cls, spreadsheet_id: str, tokens: AccessTokens) -> "SheetsClient":
        http_client = httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        return cls(spreadsheet_id, tokens, http_client)

    def tab_ids(self) -> dict[str, int]:
        body = self._request("GET", self._base_path, params={"fields": "sheets.properties"})
        return {
            sheet["properties"]["title"]: sheet["properties"]["sheetId"]
            for sheet in body.get("sheets", [])
        }

    def read_values(self, cell_range: str) -> Rows:
        body = self._request(
            "GET",
            self._values_path(cell_range),
            params={
                "valueRenderOption": "UNFORMATTED_VALUE",
                "dateTimeRenderOption": "SERIAL_NUMBER",
            },
        )
        return body.get("values", [])

    def write_values(self, cell_range: str, rows: Rows, as_formulas: bool) -> None:
        input_option = FORMULA_INPUT if as_formulas else RAW_INPUT
        self._request(
            "PUT",
            self._values_path(cell_range),
            params={"valueInputOption": input_option},
            json={"values": rows},
        )

    def write_ranges(self, rows_by_range: dict[str, Rows]) -> None:
        if not rows_by_range:
            return
        data = [{"range": cell_range, "values": rows} for cell_range, rows in rows_by_range.items()]
        self._request(
            "POST",
            f"{self._base_path}/values:batchUpdate",
            json={"valueInputOption": RAW_INPUT, "data": data},
        )

    def append_rows(self, cell_range: str, rows: Rows) -> None:
        if not rows:
            return
        self._request(
            "POST",
            f"{self._values_path(cell_range)}:append",
            params={"valueInputOption": RAW_INPUT, "insertDataOption": "INSERT_ROWS"},
            json={"values": rows},
        )

    def batch_update(self, requests: list[dict[str, Any]]) -> None:
        """Structural changes: tabs, formats, validation."""
        if not requests:
            return
        self._request("POST", f"{self._base_path}:batchUpdate", json={"requests": requests})

    def _values_path(self, cell_range: str) -> str:
        return f"{self._base_path}/values/{quote(cell_range, safe='')}"

    def _request(self, method: str, path: str, **options: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._tokens.access_token()}"}
        response = self._http_client.request(method, path, headers=headers, **options)
        if not response.is_success:
            raise SheetsError(
                f"{method} {path} failed with {response.status_code}: {response.text}"
            )
        return response.json()
