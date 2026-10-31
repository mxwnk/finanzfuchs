from datetime import date
from pathlib import Path

import pytest

from finanzfuchs.config import ConfigError, EnableBankingSettings, Settings, WebSettings

ENABLE_BANKING = {
    "ENABLE_BANKING_APPLICATION_ID": "app-id",
    "ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/app-id.pem",
    "ENABLE_BANKING_REDIRECT_URL": "https://example.org/callback",
}
WEB = {
    "FINANZFUCHS_BASE_URL": "http://finanzfuchs.home/",
    "OIDC_ISSUER": "https://id.example.org",
    "OIDC_CLIENT_ID": "client",
    "OIDC_CLIENT_SECRET": "secret",
}


class TestSettings:
    def test_applies_defaults_without_any_variable(self) -> None:
        settings = Settings.from_environment({})

        assert settings.data_dir == Path("data")
        assert settings.history_start == date(2026, 1, 1)
        assert settings.database_path == Path("data/finanzfuchs.sqlite3")

    def test_variables_override_the_defaults(self) -> None:
        environment = {
            "FINANZFUCHS_DATA_DIR": "/app/data",
            "FINANZFUCHS_HISTORY_START": "2025-07-01",
        }

        settings = Settings.from_environment(environment)

        assert settings.database_path == Path("/app/data/finanzfuchs.sqlite3")
        assert settings.history_start == date(2025, 7, 1)

    def test_rejects_an_invalid_history_start(self) -> None:
        with pytest.raises(ConfigError, match="FINANZFUCHS_HISTORY_START"):
            Settings.from_environment({"FINANZFUCHS_HISTORY_START": "1.1.2026"})


class TestWebSettings:
    def test_derives_the_callback_from_the_base_url(self) -> None:
        settings = WebSettings.from_environment(WEB)

        assert settings.redirect_uri == "http://finanzfuchs.home/auth/callback"
        assert not settings.uses_https

    def test_defaults_to_the_family_group_on_the_loopback_port(self) -> None:
        settings = WebSettings.from_environment(WEB)

        assert settings.allowed_group == "fuxbau"
        assert (settings.host, settings.port) == ("127.0.0.1", 8000)

    def test_names_every_missing_login_setting(self) -> None:
        with pytest.raises(ConfigError, match="OIDC_CLIENT_ID.*OIDC_CLIENT_SECRET"):
            WebSettings.from_environment({"FINANZFUCHS_BASE_URL": "x", "OIDC_ISSUER": "y"})

    def test_rejects_a_port_that_is_no_number(self) -> None:
        with pytest.raises(ConfigError, match="FINANZFUCHS_PORT"):
            WebSettings.from_environment(WEB | {"FINANZFUCHS_PORT": "http"})


class TestEnableBankingSettings:
    def test_reads_the_connection_and_defaults_to_the_dkb(self) -> None:
        settings = EnableBankingSettings.from_environment(ENABLE_BANKING)

        assert settings.application_id == "app-id"
        assert settings.bank_name == "DKB"

    def test_names_every_missing_setting(self) -> None:
        with pytest.raises(ConfigError, match="ENABLE_BANKING_APPLICATION_ID.*REDIRECT_URL"):
            EnableBankingSettings.from_environment(
                {"ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/app-id.pem"}
            )

    def test_reports_a_missing_private_key_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.pem"
        settings = EnableBankingSettings.from_environment(
            ENABLE_BANKING | {"ENABLE_BANKING_PRIVATE_KEY_PATH": str(missing)}
        )

        with pytest.raises(ConfigError, match="missing.pem"):
            settings.read_private_key()
