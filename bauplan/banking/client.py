"""HTTP client for the Enable Banking API (account information only)."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx

from bauplan.banking.authorization import build_application_token

API_BASE_URL = "https://api.enablebanking.com"
PERSONAL_ACCOUNTS = "personal"
REQUEST_TIMEOUT_SECONDS = 30.0

JsonObject = dict[str, Any]


class EnableBankingError(RuntimeError):
    """Enable Banking refused a request or returned something unusable."""


class EnableBankingClient:
    def __init__(
        self,
        application_id: str,
        private_key_pem: str,
        http_client: httpx.Client,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._application_id = application_id
        self._private_key_pem = private_key_pem
        self._http_client = http_client
        self._clock = clock

    @classmethod
    def connect(cls, application_id: str, private_key_pem: str) -> "EnableBankingClient":
        http_client = httpx.Client(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        return cls(application_id, private_key_pem, http_client)

    def find_bank(self, name: str, country: str) -> JsonObject:
        banks: list[JsonObject] = self._get("/aspsps", {"country": country})["aspsps"]
        for bank in banks:
            if bank["name"].casefold() == name.casefold():
                return bank
        raise EnableBankingError(_describe_unknown_bank(name, country, banks))

    def start_authorization(
        self, bank: JsonObject, consent_end: datetime, state: str, redirect_url: str
    ) -> str:
        """Returns the address where the account holder approves the access."""
        body = {
            "access": {"valid_until": consent_end.isoformat()},
            "aspsp": {"name": bank["name"], "country": bank["country"]},
            "state": state,
            "redirect_url": redirect_url,
            "psu_type": PERSONAL_ACCOUNTS,
        }
        return self._post("/auth", body)["url"]

    def create_session(self, authorization_code: str) -> JsonObject:
        return self._post("/sessions", {"code": authorization_code})

    def fetch_session(self, session_id: str) -> JsonObject:
        return self._get(f"/sessions/{session_id}")

    def fetch_balances(self, account_uid: str) -> JsonObject:
        return self._get(f"/accounts/{account_uid}/balances")

    def fetch_transaction_pages(self, account_uid: str, date_from: date) -> list[JsonObject]:
        """Returns the raw pages, so they can be archived exactly as the bank sent them."""
        pages: list[JsonObject] = []
        continuation_key: str | None = None
        while True:
            parameters = {"date_from": date_from.isoformat()}
            if continuation_key:
                parameters["continuation_key"] = continuation_key
            page = self._get(f"/accounts/{account_uid}/transactions", parameters)
            pages.append(page)
            continuation_key = page.get("continuation_key")
            if not continuation_key:
                return pages

    def _get(self, path: str, parameters: dict[str, str] | None = None) -> JsonObject:
        response = self._http_client.get(path, params=parameters, headers=self._auth_headers())
        return _read_json(response)

    def _post(self, path: str, body: JsonObject) -> JsonObject:
        response = self._http_client.post(path, json=body, headers=self._auth_headers())
        return _read_json(response)

    def _auth_headers(self) -> dict[str, str]:
        token = build_application_token(self._application_id, self._private_key_pem, self._clock())
        return {"Authorization": f"Bearer {token}"}


def _read_json(response: httpx.Response) -> JsonObject:
    if response.is_success:
        return response.json()
    request = response.request
    raise EnableBankingError(
        f"{request.method} {request.url.path} failed with {response.status_code}: {response.text}"
    )


def _describe_unknown_bank(name: str, country: str, banks: list[JsonObject]) -> str:
    similar_names = [bank["name"] for bank in banks if name.casefold() in bank["name"].casefold()]
    hint = ", ".join(similar_names) if similar_names else "none with a similar name"
    return f"Bank {name!r} not found in {country}. Similar banks: {hint}"
