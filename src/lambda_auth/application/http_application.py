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
        cors_allowed_origin: str = "",
    ) -> None:
        self._authenticate_customer = authenticate_customer
        self._token_signer = token_signer
        self._health = HealthApplication()
        self._cors_allowed_origin = cors_allowed_origin

    def execute(self, request: HttpRequest) -> HttpResponse:
        if request.path == "/health":
            return self._health.execute(request)

        if request.path == "/auth/customer/token":
            if request.method == "OPTIONS":
                return self._token_preflight(request.origin)
            if request.method != "POST":
                response = _method_not_allowed("POST")
            else:
                response = self._authenticate_customer.execute(request.body.get("cpf"))
            return self._with_token_cors(response, request.origin)

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

    def _token_preflight(self, origin: str | None) -> HttpResponse:
        headers = {
            "cache-control": "no-store",
            "vary": "Origin",
            "x-content-type-options": "nosniff",
        }
        if self._origin_is_allowed(origin):
            headers.update(
                {
                    "access-control-allow-origin": self._cors_allowed_origin,
                    "access-control-allow-credentials": "true",
                    "access-control-allow-headers": "Authorization,Content-Type,Accept",
                    "access-control-allow-methods": "POST,OPTIONS",
                }
            )
        return HttpResponse(204, MappingProxyType({}), MappingProxyType(headers))

    def _with_token_cors(self, response: HttpResponse, origin: str | None) -> HttpResponse:
        headers = dict(response.headers)
        headers["vary"] = _append_vary(headers.get("vary", ""), "Origin")
        if self._origin_is_allowed(origin):
            headers["access-control-allow-origin"] = self._cors_allowed_origin
            headers["access-control-allow-credentials"] = "true"
        return HttpResponse(
            response.status_code,
            response.body,
            MappingProxyType(headers),
        )

    def _origin_is_allowed(self, origin: str | None) -> bool:
        return bool(self._cors_allowed_origin and origin == self._cors_allowed_origin)


def _append_vary(existing: str, new_value: str) -> str:
    values = [value.strip() for value in existing.split(",") if value.strip()]
    if any(value.lower() == new_value.lower() for value in values):
        return ", ".join(values)
    return ", ".join((*values, new_value))


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
