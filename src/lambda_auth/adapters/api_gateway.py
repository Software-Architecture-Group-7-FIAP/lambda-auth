"""Adaptador de eventos HTTP do API Gateway para a porta da aplicação."""

import base64
import binascii
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
        if isinstance(path, str):
            stage = request_context.get("stage") if isinstance(request_context, Mapping) else None
            if isinstance(stage, str) and stage and stage != "$default":
                stage_prefix = f"/{stage}/"
                if path.startswith(stage_prefix):
                    path = path[len(stage) + 1 :]

    if not isinstance(method, str) or not method.strip():
        return None
    if not isinstance(path, str) or not path.startswith("/"):
        return None

    body = _body_from_event(event)
    if body is None:
        return None
    return HttpRequest(method.strip().upper(), path, body, _origin_from_event(event))


def _origin_from_event(event: Mapping[str, object]) -> str | None:
    headers = event.get("headers")
    if not isinstance(headers, Mapping):
        return None

    origin_values = [
        value
        for name, value in headers.items()
        if isinstance(name, str) and name.lower() == "origin"
    ]
    if len(origin_values) != 1 or not isinstance(origin_values[0], str):
        return None
    return origin_values[0]


def _body_from_event(event: Mapping[str, object]) -> Mapping[str, object] | None:
    raw_body = event.get("body")
    if raw_body is None or raw_body == "":
        return MappingProxyType({})
    if not isinstance(raw_body, str):
        return None

    try:
        body_bytes = (
            base64.b64decode(raw_body, validate=True)
            if event.get("isBase64Encoded") is True
            else raw_body.encode("utf-8")
        )
        parsed_body = json.loads(body_bytes.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(parsed_body, Mapping):
        return None
    return MappingProxyType(dict(parsed_body))


def _to_api_gateway_response(response: HttpResponse) -> dict[str, object]:
    return {
        "statusCode": response.status_code,
        "headers": dict(response.headers),
        "body": (
            ""
            if response.status_code == 204
            else json.dumps(dict(response.body), separators=(",", ":"))
        ),
        "isBase64Encoded": False,
    }
