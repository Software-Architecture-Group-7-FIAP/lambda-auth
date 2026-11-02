import pytest

from lambda_auth.settings import Settings


def test_settings_default_to_warning_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("JWT_ADDITIONAL_PUBLIC_KEYS_JSON", raising=False)

    settings = Settings.from_environment()

    assert settings.log_level == "WARNING"
    assert settings.jwt_ttl_seconds == 900
    assert settings.additional_public_keys == ()
    assert not settings.auth_configured


def test_settings_normalize_allowed_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "info")

    assert Settings.from_environment().log_level == "INFO"


def test_settings_reject_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "TRACE")

    with pytest.raises(ValueError, match="LOG_LEVEL"):
        Settings.from_environment()


def test_settings_load_auth_configuration_without_exposing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/auto_shop")
    monkeypatch.setenv("JWT_ISSUER", "https://auth.example.invalid")
    monkeypatch.setenv("JWT_AUDIENCE", "auto-shop-api")
    monkeypatch.setenv("JWT_TTL_SECONDS", "600")
    monkeypatch.setenv("JWT_KID", "test-key")
    monkeypatch.setenv("JWT_KMS_KEY_ID", "test-kms-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    settings = Settings.from_environment()

    assert settings.jwt_ttl_seconds == 600
    assert settings.auth_configured
    assert "postgresql://" not in repr(settings)


def test_settings_load_additional_public_keys_in_deterministic_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_KID", "active")
    monkeypatch.setenv(
        "JWT_ADDITIONAL_PUBLIC_KEYS_JSON",
        '[{"kid":"old-z","kms_key_id":"kms-z"},{"kid":"next-a","kms_key_id":"kms-a"}]',
    )

    settings = Settings.from_environment()

    assert tuple(key.kid for key in settings.additional_public_keys) == ("next-a", "old-z")
    assert tuple(key.kms_key_id for key in settings.additional_public_keys) == (
        "kms-a",
        "kms-z",
    )
    assert "kms-a" not in repr(settings)


@pytest.mark.parametrize(
    "value",
    [
        "not-json",
        "{}",
        '[{"kid":"old"}]',
        '[{"kid":"old","kms_key_id":"kms-old","extra":true}]',
        '[{"kid":" ","kms_key_id":"kms-old"}]',
        '[{"kid":"old","kms_key_id":" "}]',
        '[{"kid":1,"kms_key_id":"kms-old"}]',
        '[{"kid":"old","kms_key_id":"kms-old"},{"kid":"old","kms_key_id":"kms-2"}]',
    ],
)
def test_settings_reject_invalid_additional_public_keys(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("JWT_KID", "active")
    monkeypatch.setenv("JWT_ADDITIONAL_PUBLIC_KEYS_JSON", value)

    with pytest.raises(ValueError, match="JWT_ADDITIONAL_PUBLIC_KEYS_JSON") as error:
        Settings.from_environment()

    assert value not in str(error.value)


def test_settings_reject_additional_key_with_active_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_KID", "active")
    monkeypatch.setenv(
        "JWT_ADDITIONAL_PUBLIC_KEYS_JSON",
        '[{"kid":"active","kms_key_id":"kms-old"}]',
    )

    with pytest.raises(ValueError, match="unique"):
        Settings.from_environment()


def test_settings_accept_database_secret_id_without_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_SECRET_ID",
        "auto-shop/staging/hml/lambda-auth",
    )
    monkeypatch.setenv("JWT_ISSUER", "https://auth.example.invalid")
    monkeypatch.setenv("JWT_AUDIENCE", "auto-shop-api")
    monkeypatch.setenv("JWT_KID", "test-key")
    monkeypatch.setenv("JWT_KMS_KEY_ID", "test-kms-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    assert Settings.from_environment().auth_configured


@pytest.mark.parametrize("value", ["zero", "0", "901"])
def test_settings_reject_invalid_or_overlong_ttl(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("JWT_TTL_SECONDS", value)

    with pytest.raises(ValueError, match="JWT_TTL_SECONDS"):
        Settings.from_environment()
