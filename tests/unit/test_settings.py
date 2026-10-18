import pytest

from lambda_auth.settings import Settings


def test_settings_default_to_warning_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert Settings.from_environment().log_level == "WARNING"


def test_settings_normalize_allowed_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "info")

    assert Settings.from_environment().log_level == "INFO"


def test_settings_reject_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "TRACE")

    with pytest.raises(ValueError, match="LOG_LEVEL"):
        Settings.from_environment()
