"""Adaptador PostgreSQL de leitura para a tabela de clientes compartilhada."""

from collections.abc import Callable
from typing import Any

from lambda_auth.application.ports.database_url_provider import DatabaseUrlProvider


class PostgresCustomerRepository:
    def __init__(
        self,
        database_url: str = "",
        connect: Callable[..., Any] | None = None,
        database_url_provider: DatabaseUrlProvider | None = None,
    ) -> None:
        self._database_url = database_url
        self._connect = connect
        self._database_url_provider = database_url_provider

    def find_active_customer_id_by_cpf(self, cpf: str) -> int | None:
        database_url = (
            self._database_url_provider.get_database_url()
            if self._database_url_provider is not None
            else self._database_url
        )
        if not database_url:
            raise RuntimeError("database configuration is missing")

        connect = self._connect or _postgres_connect()
        query = """
            SELECT customers.id
            FROM customers
            JOIN customer_documents
              ON customer_documents.customer_id = customers.id
            WHERE customer_documents.document = %s
              AND customers.status = %s
            LIMIT 1
        """
        with connect(database_url, connect_timeout=3, sslmode="require") as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (cpf, "Ativo"))
                row = cursor.fetchone()

        return int(row[0]) if row is not None else None


def _postgres_connect() -> Callable[..., Any]:
    import psycopg

    return psycopg.connect
