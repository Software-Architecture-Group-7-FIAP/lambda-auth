import base64
import json
from collections.abc import Mapping
from types import MappingProxyType

import pytest

from lambda_auth.adapters.api_gateway import ApiGatewayAdapter
from lambda_auth.application.authentication import AuthenticateCustomer
from lambda_auth.application.http import HttpRequest
from lambda_auth.application.http_application import HttpApplication
from lambda_auth.settings import Settings


class FakeCustomerRepository:
    def __init__(self, customer_id: int | None = 42) -> None:
        self.customer_id = customer_id
        self.lookups: list[str] = []

    def find_active_customer_id_by_cpf(self, cpf: str) -> int | None:
        self.lookups.append(cpf)
        return self.customer_id


class FakeTokenSigner:
    def __init__(self) -> None:
        self.claims: Mapping[str, object] | None = None

    def issue(self, claims: Mapping[str, object]) -> str:
        self.claims = MappingProxyType(dict(claims))
        return "test-token"

    def get_jwks(self) -> Mapping[str, object]:
        return {"keys": [{"kty": "RSA", "kid": "test-key"}]}


def _adapter(
    repository: FakeCustomerRepository,
    signer: FakeTokenSigner,
) -> ApiGatewayAdapter:
    settings = Settings(
        log_level="WARNING",
        database_url="postgresql://localhost/auto_shop",
        jwt_issuer="https://auth.example.invalid",
        jwt_audience="auto-shop-api",
        jwt_ttl_seconds=900,
        jwt_kid="test-key",
        kms_key_id="test-kms-key",
        aws_region="us-east-1",
    )
    use_case = AuthenticateCustomer(
        repository,
        signer,
        settings,
        clock=lambda: 1_800_000_000,
        token_id_factory=lambda: "token-id",
    )
    return ApiGatewayAdapter(HttpApplication(use_case, signer))


def test_api_gateway_contract_authenticates_customer_without_echoing_cpf() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    event = {
        "httpMethod": "POST",
        "path": "/auth/customer/token",
        "body": json.dumps({"cpf": "529.982.247-25"}),
    }

    result = _adapter(repository, signer).handle(event)
    response_body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert response_body == {
        "access_token": "test-token",
        "token_type": "Bearer",
        "expires_in": 900,
    }
    assert repository.lookups == ["52998224725"]
    assert "529.982.247-25" not in json.dumps(result)
    assert "test-token" not in str(signer.claims)


def test_api_gateway_contract_accepts_base64_encoded_request_body() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    body = base64.b64encode(b'{"cpf":"52998224725"}').decode("ascii")
    event = {
        "version": "2.0",
        "rawPath": "/auth/customer/token",
        "requestContext": {"http": {"method": "POST"}},
        "body": body,
        "isBase64Encoded": True,
    }

    result = _adapter(repository, signer).handle(event)

    assert result["statusCode"] == 200
    assert repository.lookups == ["52998224725"]


@pytest.mark.parametrize("body", ["not-json", "[]"])
def test_malformed_json_body_is_rejected_before_use_case(body: str) -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    event = {
        "httpMethod": "POST",
        "path": "/auth/customer/token",
        "body": body,
    }

    result = _adapter(repository, signer).handle(event)

    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {"error": "invalid_request"}
    assert repository.lookups == []
    assert signer.claims is None


def test_jwks_endpoint_returns_public_keys_with_cache_headers() -> None:
    result = _adapter(FakeCustomerRepository(), FakeTokenSigner()).handle(
        {"httpMethod": "GET", "path": "/.well-known/jwks.json"}
    )

    assert result["statusCode"] == 200
    assert result["headers"]["cache-control"] == "public, max-age=300"
    assert json.loads(result["body"]) == {"keys": [{"kty": "RSA", "kid": "test-key"}]}


def test_http_application_rejects_wrong_auth_method() -> None:
    repository = FakeCustomerRepository()
    signer = FakeTokenSigner()
    application = HttpApplication(
        AuthenticateCustomer(repository, signer, Settings(log_level="WARNING")),
        signer,
    )

    response = application.execute(HttpRequest(method="GET", path="/auth/customer/token"))

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
    assert repository.lookups == []
