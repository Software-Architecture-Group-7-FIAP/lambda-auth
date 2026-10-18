"""Adaptador de eventos HTTP do API Gateway para a porta da aplicação."""

import json
from collections.abc import Mapping
from types import MappingProxyType

from lambda_auth.application.http import HttpRequest, HttpResponse
from lambda_auth.application.ports.application import Application


class ApiGatewayAdapter:
    def __init__(self, application: Application) -> None:
        self._application = application

    def handle(self, event: object) -> dict[str, object]:
        request = _request_from_event(event)
        response = (
            self._application.execute(request)
            if request is not None
            else HttpResponse(400, MappingProxyType({"error": "invalid_request"}))
        )
        return _to_api_gateway_response(response)


def _request_from_event(event: object) -> HttpRequest | None:
    if not isinstance(event, Mapping):
        return None

    request_context = event.get("requestContext")
    http_context = request_context.get("http") if isinstance(request_context, Mapping) else None
    if isinstance(http_context, Mapping):
        method = http_context.get("method")
        path = event.get("rawPath")
    else:
        method = event.get("httpMethod")
        path = event.get("path")

    if not isinstance(method, str) or not method.strip():
        return None
    if not isinstance(path, str) or not path.startswith("/"):
        return None

    return HttpRequest(method.strip().upper(), path)


def _to_api_gateway_response(response: HttpResponse) -> dict[str, object]:
    return {
        "statusCode": response.status_code,
        "headers": dict(response.headers),
        "body": json.dumps(dict(response.body), separators=(",", ":")),
        "isBase64Encoded": False,
    }
