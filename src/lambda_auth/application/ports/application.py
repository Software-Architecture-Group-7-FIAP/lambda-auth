"""Porta de entrada para os casos de uso acionados por eventos HTTP."""

from typing import Protocol

from lambda_auth.application.http import HttpRequest, HttpResponse


class Application(Protocol):
    def execute(self, request: HttpRequest) -> HttpResponse:
        """Execute um caso de uso para uma requisição HTTP normalizada."""
