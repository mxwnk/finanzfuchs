"""Settings from the environment (the untracked `.env` locally, the container env on the Pi)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_BANK_NAME = "DKB"
DEFAULT_DATA_DIR = "data"
DEFAULT_HISTORY_START = "2026-01-01"
DEFAULT_ALLOWED_GROUP = "fuxbau"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DATABASE_FILE_NAME = "finanzfuchs.sqlite3"
CALLBACK_PATH = "/auth/callback"
ENABLE_BANKING_VARIABLES = (
    "ENABLE_BANKING_APPLICATION_ID",
    "ENABLE_BANKING_PRIVATE_KEY_PATH",
    "ENABLE_BANKING_REDIRECT_URL",
)
WEB_VARIABLES = ("FINANZFUCHS_BASE_URL", "OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET")


class ConfigError(ValueError):
    """A setting is missing or unusable."""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    history_start: date

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "Settings":
        return cls(
            data_dir=Path(environment.get("FINANZFUCHS_DATA_DIR", DEFAULT_DATA_DIR)),
            history_start=_parse_history_start(
                environment.get("FINANZFUCHS_HISTORY_START", DEFAULT_HISTORY_START)
            ),
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / DATABASE_FILE_NAME


@dataclass(frozen=True)
class WebSettings:
    """The web app and its login through Pocket ID."""

    base_url: str
    oidc_issuer: str
    oidc_client_id: str
    oidc_client_secret: str
    allowed_group: str
    host: str
    port: int

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "WebSettings":
        _ensure_present(environment, WEB_VARIABLES)
        return cls(
            base_url=environment["FINANZFUCHS_BASE_URL"].rstrip("/"),
            oidc_issuer=environment["OIDC_ISSUER"],
            oidc_client_id=environment["OIDC_CLIENT_ID"],
            oidc_client_secret=environment["OIDC_CLIENT_SECRET"],
            allowed_group=environment.get("OIDC_ALLOWED_GROUP", DEFAULT_ALLOWED_GROUP),
            host=environment.get("FINANZFUCHS_HOST", DEFAULT_HOST),
            port=_parse_port(environment.get("FINANZFUCHS_PORT", str(DEFAULT_PORT))),
        )

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}{CALLBACK_PATH}"

    @property
    def uses_https(self) -> bool:
        return self.base_url.startswith("https://")


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
            private_key_path=Path(environment["ENABLE_BANKING_PRIVATE_KEY_PATH"]).expanduser(),
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


def _ensure_present(environment: Mapping[str, str], names: tuple[str, ...]) -> None:
    missing = [name for name in names if not environment.get(name)]
    if missing:
        raise ConfigError(f"Missing settings (see .env.example): {', '.join(missing)}")


def _parse_history_start(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ConfigError(f"FINANZFUCHS_HISTORY_START must be YYYY-MM-DD, got {text!r}") from error


def _parse_port(text: str) -> int:
    if not text.isdigit():
        raise ConfigError(f"FINANZFUCHS_PORT must be a number, got {text!r}")
    return int(text)
