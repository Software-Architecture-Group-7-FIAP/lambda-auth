"""Adaptador PostgreSQL de leitura para a tabela de clientes compartilhada."""

from collections.abc import Callable
from typing import Any


class PostgresCustomerRepository:
    def __init__(
        self,
        database_url: str,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._database_url = database_url
        self._connect = connect

    def find_active_customer_id_by_cpf(self, cpf: str) -> int | None:
        if not self._database_url:
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
        with connect(self._database_url, connect_timeout=3, sslmode="require") as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (cpf, "Ativo"))
                row = cursor.fetchone()

        return int(row[0]) if row is not None else None


def _postgres_connect() -> Callable[..., Any]:
    import psycopg

    return psycopg.connect
