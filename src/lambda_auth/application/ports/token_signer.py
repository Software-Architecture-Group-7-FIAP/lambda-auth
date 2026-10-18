"""Porta de emissão e publicação de chaves JWT."""

from collections.abc import Mapping
from typing import Protocol


class TokenSigner(Protocol):
    def issue(self, claims: Mapping[str, object]) -> str:
        """Assine as claims e retorne um JWT compacto."""

    def get_jwks(self) -> Mapping[str, object]:
        """Retorne o conjunto de chaves públicas usado para validar os tokens."""
