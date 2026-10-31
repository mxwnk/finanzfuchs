"""Files on disk: the bank session and every raw bank response.

Banks usually return only the last 90 days, so a raw response is the only lasting copy of older
transactions. Files are written once and never overwritten.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from finanzfuchs.config import ConfigError

SESSION_FILE_NAME = "session.json"
OWNER_ONLY = 0o600
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

JsonObject = dict[str, Any]


class RawArchive:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def save_session(self, session: JsonObject) -> None:
        session_file = self._data_dir / SESSION_FILE_NAME
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session, indent=2))
        session_file.chmod(OWNER_ONLY)

    def load_session(self) -> JsonObject:
        session_file = self._data_dir / SESSION_FILE_NAME
        if not session_file.exists():
            raise ConfigError(f"No bank session at {session_file}; run `finanzfuchs connect` first")
        return json.loads(session_file.read_text())

    def save_transaction_pages(
        self, account_uid: str, pages: list[JsonObject], fetched_at: datetime
    ) -> Path:
        return self._write_once("transactions", account_uid, pages, fetched_at)

    def save_balances(self, account_uid: str, balances: JsonObject, fetched_at: datetime) -> Path:
        return self._write_once("balances", account_uid, balances, fetched_at)

    def _write_once(
        self, kind: str, account_uid: str, content: object, fetched_at: datetime
    ) -> Path:
        target = self._data_dir / "raw" / kind / account_uid / _file_name(fetched_at)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x") as file:
            json.dump(content, file, indent=2, ensure_ascii=False)
        return target


def _file_name(fetched_at: datetime) -> str:
    return f"{fetched_at.strftime(TIMESTAMP_FORMAT)}.json"
