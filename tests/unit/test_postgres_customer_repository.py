from collections.abc import Callable
from typing import Any

import pytest

from lambda_auth.adapters.postgres_customer_repository import PostgresCustomerRepository


class FakeCursor:
    def __init__(self, row: tuple[int] | None) -> None:
        self.row = row
        self.query: str | None = None
        self.parameters: tuple[str, str] | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, query: str, parameters: tuple[str, str]) -> None:
        self.query = query
        self.parameters = parameters

    def fetchone(self) -> tuple[int] | None:
        return self.row


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def cursor(self) -> FakeCursor:
        return self._cursor


def _connect_factory(
    cursor: FakeCursor,
    captured: dict[str, object],
) -> Callable[..., Any]:
    def connect(database_url: str, **options: object) -> FakeConnection:
        captured["database_url"] = database_url
        captured["options"] = options
        return FakeConnection(cursor)

    return connect


def test_repository_uses_parameterized_query_for_active_customer() -> None:
    cursor = FakeCursor((42,))
    captured: dict[str, object] = {}
    repository = PostgresCustomerRepository(
        "postgresql://localhost/auto_shop",
        connect=_connect_factory(cursor, captured),
    )

    customer_id = repository.find_active_customer_id_by_cpf("52998224725")

    assert customer_id == 42
    assert cursor.query is not None
    assert "JOIN customer_documents" in cursor.query
    assert "customers.status = %s" in cursor.query
    assert cursor.parameters == ("52998224725", "Ativo")
    assert captured["options"] == {"connect_timeout": 3, "sslmode": "require"}


def test_repository_returns_none_for_missing_or_inactive_customer() -> None:
    cursor = FakeCursor(None)
    repository = PostgresCustomerRepository(
        "postgresql://localhost/auto_shop",
        connect=_connect_factory(cursor, {}),
    )

    assert repository.find_active_customer_id_by_cpf("52998224725") is None


def test_repository_rejects_missing_connection_configuration() -> None:
    repository = PostgresCustomerRepository("")

    with pytest.raises(RuntimeError, match="configuration"):
        repository.find_active_customer_id_by_cpf("52998224725")
