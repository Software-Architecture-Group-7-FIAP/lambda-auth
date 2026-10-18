import json

import pytest

from lambda_auth.adapters.secrets_manager_database_url import SecretsManagerDatabaseUrl


class FakeSecretsManagerClient:
    def __init__(self, secret_value: str) -> None:
        self.secret_value = secret_value
        self.calls: list[str] = []

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        self.calls.append(SecretId)
        return {"SecretString": self.secret_value}


def test_provider_reads_database_url_from_secret_json() -> None:
    client = FakeSecretsManagerClient(
        json.dumps({"DATABASE_URL": "postgresql://localhost/auto_shop"})
    )
    provider = SecretsManagerDatabaseUrl(
        "secret-arn",
        "us-east-1",
        secrets_client=client,
        clock=lambda: 10.0,
    )

    assert provider.get_database_url() == "postgresql://localhost/auto_shop"
    assert client.calls == ["secret-arn"]


def test_provider_caches_secret_for_five_minutes_and_refreshes_after_expiry() -> None:
    client = FakeSecretsManagerClient("postgresql://localhost/auto_shop")
    clock_value = {"now": 100.0}
    provider = SecretsManagerDatabaseUrl(
        "secret-arn",
        "us-east-1",
        secrets_client=client,
        clock=lambda: clock_value["now"],
    )

    assert provider.get_database_url() == "postgresql://localhost/auto_shop"
    clock_value["now"] += 299
    assert provider.get_database_url() == "postgresql://localhost/auto_shop"
    assert client.calls == ["secret-arn"]

    clock_value["now"] += 2
    assert provider.get_database_url() == "postgresql://localhost/auto_shop"
    assert client.calls == ["secret-arn", "secret-arn"]


def test_provider_rejects_invalid_secret_without_exposing_its_value() -> None:
    secret_value = json.dumps({"unexpected": "not-a-real-credential"})
    provider = SecretsManagerDatabaseUrl(
        "secret-arn",
        "us-east-1",
        secrets_client=FakeSecretsManagerClient(secret_value),
    )

    with pytest.raises(RuntimeError, match="format") as error:
        provider.get_database_url()

    assert "not-a-real-credential" not in str(error.value)


def test_provider_rejects_incomplete_configuration_before_aws_call() -> None:
    provider = SecretsManagerDatabaseUrl("", "")

    with pytest.raises(RuntimeError, match="configuration"):
        provider.get_database_url()
