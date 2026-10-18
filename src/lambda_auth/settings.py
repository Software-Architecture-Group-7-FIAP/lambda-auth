"""Configuração segura lida do ambiente de execução."""

import os
from dataclasses import dataclass

_ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class Settings:
    log_level: str

    @classmethod
    def from_environment(cls) -> "Settings":
        log_level = os.environ.get("LOG_LEVEL", "WARNING").strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL deve ser um destes valores: {allowed}")
        return cls(log_level=log_level)
