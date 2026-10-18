"""Porta de leitura dos clientes habilitados para autenticação."""

from typing import Protocol


class CustomerRepository(Protocol):
    def find_active_customer_id_by_cpf(self, cpf: str) -> int | None:
        """Retorne apenas o ID de um cliente ativo associado ao CPF normalizado."""
