"""Caso de uso mínimo para verificar se o handler está disponível."""

from types import MappingProxyType

from lambda_auth.application.http import HttpRequest, HttpResponse


class HealthApplication:
    def execute(self, request: HttpRequest) -> HttpResponse:
        if request.path != "/health":
            return HttpResponse(404, MappingProxyType({"error": "not_found"}))

        if request.method != "GET":
            return HttpResponse(
                405,
                MappingProxyType({"error": "method_not_allowed"}),
                MappingProxyType(
                    {
                        "content-type": "application/json; charset=utf-8",
                        "cache-control": "no-store",
                        "x-content-type-options": "nosniff",
                        "allow": "GET",
                    }
                ),
            )

        return HttpResponse(200, MappingProxyType({"status": "ok"}))
