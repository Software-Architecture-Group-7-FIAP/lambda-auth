"""Caso de uso para autenticar clientes e emitir credenciais temporárias."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import uuid4

from lambda_auth.application.cpf import normalize_valid_cpf
from lambda_auth.application.http import HttpResponse
from lambda_auth.application.ports.customer_repository import CustomerRepository
from lambda_auth.application.ports.token_signer import TokenSigner
from lambda_auth.settings import Settings


class AuthenticateCustomer:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        token_signer: TokenSigner,
        settings: Settings,
        clock: Callable[[], int] | None = None,
        token_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._customer_repository = customer_repository
        self._token_signer = token_signer
        self._settings = settings
        self._clock = clock or (lambda: int(datetime.now(UTC).timestamp()))
        self._token_id_factory = token_id_factory or (lambda: str(uuid4()))

    def execute(self, cpf_value: object) -> HttpResponse:
        cpf = normalize_valid_cpf(cpf_value)
        if cpf is None:
            return HttpResponse(422, MappingProxyType({"error": "invalid_cpf"}))

        if not self._settings.auth_configured:
            return _service_unavailable()

        try:
            customer_id = self._customer_repository.find_active_customer_id_by_cpf(cpf)
        except Exception:
            return _service_unavailable()

        if customer_id is None:
            return HttpResponse(401, MappingProxyType({"error": "invalid_credentials"}))

        issued_at = self._clock()
        claims: Mapping[str, object] = MappingProxyType(
            {
                "sub": str(customer_id),
                "principal_type": "customer",
                "scope": "customer",
                "iss": self._settings.jwt_issuer,
                "aud": self._settings.jwt_audience,
                "iat": issued_at,
                "exp": issued_at + self._settings.jwt_ttl_seconds,
                "jti": self._token_id_factory(),
            }
        )

        try:
            access_token = self._token_signer.issue(claims)
        except Exception:
            return _service_unavailable()

        return HttpResponse(
            200,
            MappingProxyType(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": self._settings.jwt_ttl_seconds,
                }
            ),
        )


def _service_unavailable() -> HttpResponse:
    return HttpResponse(503, MappingProxyType({"error": "service_unavailable"}))
