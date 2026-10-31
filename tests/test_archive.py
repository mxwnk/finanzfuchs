import json
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bauplan.archive import RawArchive
from bauplan.config import ConfigError

FETCHED_AT = datetime(2026, 11, 1, 6, 0, 5, tzinfo=UTC)


def test_keeps_the_session_readable_only_for_the_owner(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)

    archive.save_session({"session_id": "s1"})

    session_file = tmp_path / "session.json"
    assert stat.S_IMODE(session_file.stat().st_mode) == 0o600


def test_returns_the_saved_session(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)
    archive.save_session({"session_id": "s1", "accounts": []})

    session = archive.load_session()

    assert session == {"session_id": "s1", "accounts": []}


def test_asks_to_connect_when_no_session_exists(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="connect"):
        RawArchive(tmp_path).load_session()


def test_stores_every_transaction_fetch_per_account_and_time(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)
    pages = [{"transactions": [{"transaction_id": "1"}]}]

    stored_file = archive.save_transaction_pages("uid-1", pages, FETCHED_AT)

    assert stored_file == tmp_path / "raw" / "transactions" / "uid-1" / "20261101T060005Z.json"
    assert json.loads(stored_file.read_text()) == pages


def test_never_overwrites_an_earlier_fetch(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)
    archive.save_transaction_pages("uid-1", [{"transactions": []}], FETCHED_AT)

    with pytest.raises(FileExistsError):
        archive.save_transaction_pages("uid-1", [{"transactions": []}], FETCHED_AT)


def test_stores_balances_next_to_the_transactions(tmp_path: Path) -> None:
    archive = RawArchive(tmp_path)

    stored_file = archive.save_balances("uid-1", {"balances": []}, FETCHED_AT)

    assert stored_file == tmp_path / "raw" / "balances" / "uid-1" / "20261101T060005Z.json"
