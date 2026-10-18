import json
from types import MappingProxyType

import pytest

from lambda_auth.adapters.api_gateway import ApiGatewayAdapter
from lambda_auth.application.http import HttpRequest, HttpResponse


class FakeApplication:
    def __init__(self) -> None:
        self.request: HttpRequest | None = None

    def execute(self, request: HttpRequest) -> HttpResponse:
        self.request = request
        return HttpResponse(
            200,
            MappingProxyType({"method": request.method, "path": request.path}),
        )


@pytest.mark.parametrize(
    ("event", "expected_request"),
    [
        (
            {
                "httpMethod": "get",
                "path": "/health",
                "body": json.dumps({"cpf": "529.982.247-25"}),
            },
            HttpRequest(
                method="GET",
                path="/health",
                body=MappingProxyType({"cpf": "529.982.247-25"}),
            ),
        ),
        (
            {
                "rawPath": "/health",
                "requestContext": {"http": {"method": "GET"}},
            },
            HttpRequest(method="GET", path="/health"),
        ),
    ],
)
def test_adapter_maps_api_gateway_events_without_echoing_input(
    event: dict[str, object], expected_request: HttpRequest
) -> None:
    application = FakeApplication()
    result = ApiGatewayAdapter(application).handle(event)

    assert application.request == expected_request
    assert result["statusCode"] == 200
    assert result["headers"]["content-type"] == "application/json; charset=utf-8"
    assert json.loads(result["body"]) == {"method": "GET", "path": "/health"}
    assert "529.982.247-25" not in json.dumps(result)
    assert result["isBase64Encoded"] is False


@pytest.mark.parametrize(
    "event",
    [
        None,
        [],
        {},
        {"httpMethod": "GET"},
        {"httpMethod": "GET", "path": "health"},
        {"httpMethod": "GET", "path": "/health", "body": "not-json"},
        {"httpMethod": "GET", "path": "/health", "body": []},
    ],
)
def test_adapter_rejects_malformed_events_without_calling_application(
    event: object,
) -> None:
    application = FakeApplication()
    result = ApiGatewayAdapter(application).handle(event)

    assert result["statusCode"] == 400
    assert json.loads(result["body"]) == {"error": "invalid_request"}
    assert application.request is None
