"""Un Ronspot en memoria que responde con las capturas reales del portal."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import requests

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.status_code = status

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeCookies(dict[str, str]):
    def set(self, name: str, value: str, **kwargs: object) -> None:
        self[name] = value


class FakeRonspot:
    def __init__(
        self,
        *,
        weeks: dict[str, str] | None = None,
        claim: str = "claim_ok.json",
        bookable: set[str] | None = None,
        pending: list[str] | None = None,
        release: str = "release_ok.json",
        status: int = 200,
        vehicles_status: int | None = None,
        vehicles_body: str | None = None,
        offline: bool = False,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.cookies = FakeCookies()
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._weeks = weeks or {}
        self._claim = claim
        self._bookable = bookable if bookable is not None else set()
        self._pending = list(pending or ["pending_ok.json"])
        self._release = release
        self._status = status
        self._vehicles_status = vehicles_status
        self._vehicles_body = vehicles_body
        self._offline = offline

    def post(self, url, data=None, timeout=None, **kwargs):
        path = urlsplit(url).path
        fields = {k: str(v) for k, v in (data or {}).items()}
        self.calls.append((path, fields))
        if self._offline:
            raise requests.ConnectionError("el router se está reiniciando")
        if self._status != 200:
            return FakeResponse("", self._status)
        if path.endswith("GetAvalablevehicleTypeDayWise"):
            if self._vehicles_status is not None:
                return FakeResponse(self._vehicles_body or "", self._vehicles_status)
            if self._vehicles_body is not None:
                return FakeResponse(self._vehicles_body)
            if fields.get("booking_date") in self._bookable:
                return FakeResponse(
                    '<select name="vehicletype"><option value="2">TESTPLATE</option></select>'
                )
            return FakeResponse("0")
        if path.endswith("claimSpot"):
            return FakeResponse(fixture(self._claim))
        if path.endswith("getPendingClaimStatus"):
            name = self._pending.pop(0) if len(self._pending) > 1 else self._pending[0]
            # La captura es del 5-oct; el servidor real contesta sobre la fecha preguntada.
            return FakeResponse(fixture(name).replace("2026-10-05", fields["date"]))
        if path.endswith("releaseAssignSpot"):
            return FakeResponse(fixture(self._release))
        if path.endswith("Claim_release"):
            name = self._weeks.get(fields.get("StartDate", ""), "week_full.json")
            return FakeResponse(fixture(name))
        raise AssertionError(f"ruta no prevista: {path}")

    def paths(self) -> list[str]:
        return [p for p, _ in self.calls]

    def body(self, suffix: str) -> dict[str, str]:
        for path, fields in self.calls:
            if path.endswith(suffix):
                return fields
        raise AssertionError(f"no se ha llamado a {suffix}")


class FakeSlack:
    def __init__(self, *, working: bool = True) -> None:
        self.messages: list[str] = []
        self.working = working

    def send(self, text: str) -> bool:
        self.messages.append(text)
        return self.working
