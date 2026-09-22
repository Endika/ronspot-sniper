"""All these adapters need from `requests.Session`, so a test can stand in for it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> Any: ...


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        json: Any = ...,
        headers: Mapping[str, str] | None = ...,
        timeout: float | None = ...,
    ) -> HttpResponse: ...
