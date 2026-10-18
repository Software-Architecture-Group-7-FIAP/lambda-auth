"""Porta para obter a URL de conexão sem expor credenciais à aplicação."""

from typing import Protocol


class DatabaseUrlProvider(Protocol):
    def get_database_url(self) -> str:
        """Retorne uma URL PostgreSQL fornecida por configuração segura."""
