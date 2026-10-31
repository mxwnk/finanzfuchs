"""Settings from the environment (the untracked `.env` locally, the container env on the NUC)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_BANK_NAME = "DKB"
DEFAULT_DATA_DIR = "data"
DEFAULT_HISTORY_START = "2026-01-01"
ENABLE_BANKING_VARIABLES = (
    "ENABLE_BANKING_APPLICATION_ID",
    "ENABLE_BANKING_PRIVATE_KEY_PATH",
    "ENABLE_BANKING_REDIRECT_URL",
)


SHEET_VARIABLES = ("GOOGLE_SERVICE_ACCOUNT_FILE", "BAUPLAN_SPREADSHEET_ID")


class ConfigError(ValueError):
    """A setting is missing or unusable."""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    history_start: date

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "Settings":
        return cls(
            data_dir=Path(environment.get("BAUPLAN_DATA_DIR", DEFAULT_DATA_DIR)),
            history_start=_parse_history_start(
                environment.get("BAUPLAN_HISTORY_START", DEFAULT_HISTORY_START)
            ),
        )


@dataclass(frozen=True)
class EnableBankingSettings:
    """Only the bank connection needs these; imports from files work without them."""

    application_id: str
    private_key_path: Path
    redirect_url: str
    bank_name: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "EnableBankingSettings":
        _ensure_present(environment, ENABLE_BANKING_VARIABLES)
        return cls(
            application_id=environment["ENABLE_BANKING_APPLICATION_ID"],
            private_key_path=Path(environment["ENABLE_BANKING_PRIVATE_KEY_PATH"]),
            redirect_url=environment["ENABLE_BANKING_REDIRECT_URL"],
            bank_name=environment.get("ENABLE_BANKING_BANK_NAME", DEFAULT_BANK_NAME),
        )

    def read_private_key(self) -> str:
        try:
            return self.private_key_path.read_text()
        except OSError as error:
            raise ConfigError(
                f"Cannot read the Enable Banking private key at {self.private_key_path}: {error}"
            ) from error


@dataclass(frozen=True)
class SheetSettings:
    """Only the sheet commands need these."""

    service_account_file: Path
    spreadsheet_id: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "SheetSettings":
        _ensure_present(environment, SHEET_VARIABLES)
        return cls(
            service_account_file=Path(environment["GOOGLE_SERVICE_ACCOUNT_FILE"]).expanduser(),
            spreadsheet_id=environment["BAUPLAN_SPREADSHEET_ID"],
        )


def _ensure_present(environment: Mapping[str, str], names: tuple[str, ...]) -> None:
    missing = [name for name in names if not environment.get(name)]
    if missing:
        raise ConfigError(f"Missing settings (see .env.example): {', '.join(missing)}")


def _parse_history_start(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ConfigError(f"BAUPLAN_HISTORY_START must be YYYY-MM-DD, got {text!r}") from error
