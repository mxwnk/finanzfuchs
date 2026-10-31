from datetime import date
from pathlib import Path

import pytest

from bauplan.config import ConfigError, EnableBankingSettings, Settings, SheetSettings

ENABLE_BANKING = {
    "ENABLE_BANKING_APPLICATION_ID": "app-id",
    "ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/app-id.pem",
    "ENABLE_BANKING_REDIRECT_URL": "https://fuxbau.org/bauplan/callback",
}


class TestSettings:
    def test_applies_defaults_without_any_variable(self) -> None:
        settings = Settings.from_environment({})

        assert settings.data_dir == Path("data")
        assert settings.history_start == date(2026, 1, 1)

    def test_variables_override_the_defaults(self) -> None:
        environment = {"BAUPLAN_DATA_DIR": "/srv/bauplan", "BAUPLAN_HISTORY_START": "2025-07-01"}

        settings = Settings.from_environment(environment)

        assert settings.data_dir == Path("/srv/bauplan")
        assert settings.history_start == date(2025, 7, 1)

    def test_rejects_an_invalid_history_start(self) -> None:
        with pytest.raises(ConfigError, match="BAUPLAN_HISTORY_START"):
            Settings.from_environment({"BAUPLAN_HISTORY_START": "1.1.2026"})


class TestEnableBankingSettings:
    def test_reads_the_connection_and_defaults_to_the_dkb(self) -> None:
        settings = EnableBankingSettings.from_environment(ENABLE_BANKING)

        assert settings.application_id == "app-id"
        assert settings.private_key_path == Path("/keys/app-id.pem")
        assert settings.bank_name == "DKB"

    def test_names_every_missing_setting(self) -> None:
        with pytest.raises(ConfigError, match="ENABLE_BANKING_APPLICATION_ID.*REDIRECT_URL"):
            EnableBankingSettings.from_environment(
                {"ENABLE_BANKING_PRIVATE_KEY_PATH": "/keys/app-id.pem"}
            )

    def test_reads_the_private_key_file(self, tmp_path: Path) -> None:
        key_file = tmp_path / "app-id.pem"
        key_file.write_text("-----BEGIN PRIVATE KEY-----")
        settings = EnableBankingSettings.from_environment(
            ENABLE_BANKING | {"ENABLE_BANKING_PRIVATE_KEY_PATH": str(key_file)}
        )

        assert settings.read_private_key() == "-----BEGIN PRIVATE KEY-----"

    def test_reports_a_missing_private_key_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.pem"
        settings = EnableBankingSettings.from_environment(
            ENABLE_BANKING | {"ENABLE_BANKING_PRIVATE_KEY_PATH": str(missing)}
        )

        with pytest.raises(ConfigError, match="missing.pem"):
            settings.read_private_key()


class TestSheetSettings:
    def test_reads_the_key_file_and_the_spreadsheet(self) -> None:
        settings = SheetSettings.from_environment(
            {"GOOGLE_SERVICE_ACCOUNT_FILE": "/keys/bauplan.json", "BAUPLAN_SPREADSHEET_ID": "abc"}
        )

        assert settings.service_account_file == Path("/keys/bauplan.json")
        assert settings.spreadsheet_id == "abc"

    def test_expands_the_home_directory_in_the_key_path(self) -> None:
        settings = SheetSettings.from_environment(
            {"GOOGLE_SERVICE_ACCOUNT_FILE": "~/keys/bauplan.json", "BAUPLAN_SPREADSHEET_ID": "abc"}
        )

        assert settings.service_account_file == Path.home() / "keys" / "bauplan.json"

    def test_names_the_missing_spreadsheet(self) -> None:
        with pytest.raises(ConfigError, match="BAUPLAN_SPREADSHEET_ID"):
            SheetSettings.from_environment({"GOOGLE_SERVICE_ACCOUNT_FILE": "/keys/bauplan.json"})
