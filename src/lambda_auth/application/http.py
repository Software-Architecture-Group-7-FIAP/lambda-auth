"""Tipos HTTP internos usados entre o adaptador e a aplicação."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

DEFAULT_HEADERS: Mapping[str, str] = MappingProxyType(
    {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
    }
)
EMPTY_BODY: Mapping[str, object] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    path: str
    body: Mapping[str, object] = field(default_factory=lambda: EMPTY_BODY)
    origin: str | None = None


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    body: Mapping[str, object]
    headers: Mapping[str, str] = field(default_factory=lambda: DEFAULT_HEADERS)
