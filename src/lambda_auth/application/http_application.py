"""Roteamento HTTP interno para saúde, autenticação e chaves públicas."""

from types import MappingProxyType

from lambda_auth.application.authentication import AuthenticateCustomer
from lambda_auth.application.health import HealthApplication
from lambda_auth.application.http import HttpRequest, HttpResponse
from lambda_auth.application.ports.token_signer import TokenSigner


class HttpApplication:
    def __init__(
        self,
        authenticate_customer: AuthenticateCustomer,
        token_signer: TokenSigner,
    ) -> None:
        self._authenticate_customer = authenticate_customer
        self._token_signer = token_signer
        self._health = HealthApplication()

    def execute(self, request: HttpRequest) -> HttpResponse:
        if request.path == "/health":
            return self._health.execute(request)

        if request.path == "/auth/customer/token":
            if request.method != "POST":
                return _method_not_allowed("POST")
            return self._authenticate_customer.execute(request.body.get("cpf"))

        if request.path == "/.well-known/jwks.json":
            if request.method != "GET":
                return _method_not_allowed("GET")
            try:
                jwks = self._token_signer.get_jwks()
            except Exception:
                return HttpResponse(503, MappingProxyType({"error": "service_unavailable"}))
            return HttpResponse(
                200,
                MappingProxyType(dict(jwks)),
                MappingProxyType(
                    {
                        "content-type": "application/json; charset=utf-8",
                        "cache-control": "public, max-age=300",
                        "x-content-type-options": "nosniff",
                    }
                ),
            )

        return HttpResponse(404, MappingProxyType({"error": "not_found"}))


def _method_not_allowed(allowed_method: str) -> HttpResponse:
    return HttpResponse(
        405,
        MappingProxyType({"error": "method_not_allowed"}),
        MappingProxyType(
            {
                "content-type": "application/json; charset=utf-8",
                "cache-control": "no-store",
                "x-content-type-options": "nosniff",
                "allow": allowed_method,
            }
        ),
    )
