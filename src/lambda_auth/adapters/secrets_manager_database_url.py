"""Adaptador lazy e cacheado para credenciais PostgreSQL no Secrets Manager."""

import json
from collections.abc import Callable, Mapping
from time import monotonic
from typing import Any

from botocore.config import Config

_AWS_CLIENT_CONFIG = Config(
    connect_timeout=1,
    read_timeout=3,
    retries={"mode": "standard", "total_max_attempts": 1},
)


class SecretsManagerDatabaseUrl:
    def __init__(
        self,
        secret_id: str,
        region: str,
        secrets_client: Any | None = None,
        clock: Callable[[], float] | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._secret_id = secret_id
        self._region = region
        self._secrets_client = secrets_client
        self._clock = clock or monotonic
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_database_url: str | None = None
        self._cached_at: float | None = None

    def get_database_url(self) -> str:
        current_time = self._clock()
        if (
            self._cached_database_url is not None
            and self._cached_at is not None
            and current_time - self._cached_at < self._cache_ttl_seconds
        ):
            return self._cached_database_url

        if not self._secret_id or not self._region:
            raise RuntimeError("database secret configuration is incomplete")

        secret_response = self._client().get_secret_value(SecretId=self._secret_id)
        secret_value = secret_response.get("SecretString")
        if not isinstance(secret_value, str):
            raise RuntimeError("database secret is unavailable")

        database_url = _database_url_from_secret(secret_value)
        self._cached_database_url = database_url
        self._cached_at = current_time
        return database_url

    def _client(self) -> Any:
        if self._secrets_client is None:
            import boto3

            self._secrets_client = boto3.client(
                "secretsmanager",
                region_name=self._region,
                config=_AWS_CLIENT_CONFIG,
            )
        return self._secrets_client


def _database_url_from_secret(secret_value: str) -> str:
    value = secret_value
    if secret_value.lstrip().startswith("{"):
        try:
            parsed_secret = json.loads(secret_value)
        except json.JSONDecodeError:
            raise RuntimeError("database secret format is invalid") from None
        value = parsed_secret.get("DATABASE_URL") if isinstance(parsed_secret, Mapping) else ""

    if not isinstance(value, str) or not value.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("database secret format is invalid")
    return value
