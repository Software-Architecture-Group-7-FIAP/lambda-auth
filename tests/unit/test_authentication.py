from collections.abc import Mapping
from types import MappingProxyType

import pytest

from lambda_auth.application.authentication import AuthenticateCustomer
from lambda_auth.application.http import HttpResponse
from lambda_auth.settings import Settings


class FakeCustomerRepository:
    def __init__(self, customer_id: int | None = 42, error: Exception | None = None) -> None:
        self.customer_id = customer_id
        self.error = error
        self.lookups: list[str] = []

    def find_active_customer_id_by_cpf(self, cpf: str) -> int | None:
        self.lookups.append(cpf)
        if self.error is not None:
            raise self.error
        return self.customer_id


class FakeTokenSigner:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.claims: Mapping[str, object] | None = None

    def issue(self, claims: Mapping[str, object]) -> str:
        if self.error is not None:
            raise self.error
        self.claims = MappingProxyType(dict(claims))
        return "signed-token-placeholder"

    def get_jwks(self) -> Mapping[str, object]:
        return {"keys": []}


def _settings() -> Settings:
    return Settings(
        log_level="WARNING",
        database_url="postgresql://localhost/auto_shop",
        jwt_issuer="https://auth.example.invalid",
        jwt_audience="auto-shop-api",
        jwt_ttl_seconds=900,
        jwt_kid="test-key",
        kms_key_id="test-key-id",
        aws_region="us-east-1",
    )


def test_active_customer_receives_token_with_only_allowed_claims() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    use_case = AuthenticateCustomer(
        repository,
        signer,
        _settings(),
        clock=lambda: 1_800_000_000,
        token_id_factory=lambda: "token-id",
    )

    response = use_case.execute("529.982.247-25")

    assert response.status_code == 200
    assert response.body == {
        "access_token": "signed-token-placeholder",
        "token_type": "Bearer",
        "expires_in": 900,
    }
    assert repository.lookups == ["52998224725"]
    assert signer.claims == {
        "sub": "42",
        "principal_type": "customer",
        "scope": "customer",
        "iss": "https://auth.example.invalid",
        "aud": "auto-shop-api",
        "iat": 1_800_000_000,
        "exp": 1_800_000_900,
        "jti": "token-id",
    }
    assert set(signer.claims or {}) == {
        "sub",
        "principal_type",
        "scope",
        "iss",
        "aud",
        "iat",
        "exp",
        "jti",
    }
    assert "529.982.247-25" not in str(signer.claims)


def test_invalid_cpf_does_not_query_repository_or_sign_token() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()

    response = AuthenticateCustomer(repository, signer, _settings()).execute("111.111.111-11")

    assert response == HttpResponse(422, MappingProxyType({"error": "invalid_cpf"}))
    assert repository.lookups == []
    assert signer.claims is None


@pytest.mark.parametrize("customer_id", [None])
def test_unknown_and_inactive_customers_share_public_response(customer_id: int | None) -> None:
    first_signer = FakeTokenSigner()
    second_signer = FakeTokenSigner()
    first = AuthenticateCustomer(
        FakeCustomerRepository(customer_id), first_signer, _settings()
    ).execute("52998224725")
    second = AuthenticateCustomer(
        FakeCustomerRepository(customer_id), second_signer, _settings()
    ).execute("11144477735")

    assert first.status_code == second.status_code == 401
    assert first.body == second.body == {"error": "invalid_credentials"}
    assert first_signer.claims is second_signer.claims is None


def test_repository_failure_returns_generic_service_error() -> None:
    response = AuthenticateCustomer(
        FakeCustomerRepository(error=RuntimeError("database detail")),
        FakeTokenSigner(),
        _settings(),
    ).execute("52998224725")

    assert response.status_code == 503
    assert response.body == {"error": "service_unavailable"}
    assert "database detail" not in str(response.body)


def test_signing_failure_returns_generic_service_error() -> None:
    response = AuthenticateCustomer(
        FakeCustomerRepository(),
        FakeTokenSigner(error=RuntimeError("signing detail")),
        _settings(),
    ).execute("52998224725")

    assert response.status_code == 503
    assert response.body == {"error": "service_unavailable"}
    assert "signing detail" not in str(response.body)


def test_missing_auth_configuration_does_not_query_or_sign() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    settings = Settings(log_level="WARNING")

    response = AuthenticateCustomer(repository, signer, settings).execute("52998224725")

    assert response.status_code == 503
    assert repository.lookups == []
    assert signer.claims is None
