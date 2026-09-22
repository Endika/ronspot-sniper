"""Stand-ins for the two ports, plus an HTTP transport fed with real portal captures."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from ronspot_sniper.domain import Booking, Day, Week
from ronspot_sniper.ports import ClaimResult, GatewayError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def day(
    iso: str, *, mine: bool = False, blocked: bool = False, free: bool = False, bay: str = ""
) -> Day:
    return Day(
        date=dt.date.fromisoformat(iso),
        free_bays=1 if free else 0,
        spot_id=25219 if mine else 0,
        bay=bay or ("22 Level 4" if mine else ""),
        blocked=blocked,
        calendar_says_free=free,
    )


class FakeGateway:
    """A parking service in memory. Records what was asked of it."""

    def __init__(
        self,
        days: list[Day] | None = None,
        *,
        bookable: set[str] | None = None,
        claim_accepted: bool = True,
        confirms: bool = True,
        raises: GatewayError | None = None,
        raises_on: str = "week",
    ) -> None:
        self.days = days or []
        self._bookable = bookable or set()
        self._claim_accepted = claim_accepted
        self._confirms = confirms
        self._raises = raises
        self._raises_on = raises_on
        self.calls: list[tuple[str, str]] = []

    def _maybe_raise(self, what: str) -> None:
        self.calls.append((what, ""))
        if self._raises is not None and self._raises_on == what:
            raise self._raises

    def week(self, start: dt.date) -> Week:
        self._maybe_raise("week")
        end = start + dt.timedelta(days=7)
        return Week(start, tuple(d for d in self.days if start <= d.date < end))

    def bookable(self, date: dt.date) -> bool:
        self._maybe_raise("bookable")
        return date.isoformat() in self._bookable

    def claim(self, date: dt.date) -> ClaimResult:
        self._maybe_raise("claim")
        return ClaimResult(self._claim_accepted, "Success" if self._claim_accepted else "no room")

    def confirm(self, date: dt.date, *, tries: int = 8, gap: float = 1.5) -> Booking | None:
        self._maybe_raise("confirm")
        return Booking(date, 25228, "11 Level 3") if self._confirms else None

    def release(self, booking: Booking) -> bool:
        self._maybe_raise("release")
        return True

    def did(self, what: str) -> bool:
        return any(name == what for name, _ in self.calls)


class FakeNotifier:
    def __init__(self, *, working: bool = True) -> None:
        self.messages: list[str] = []
        self.working = working

    def send(self, text: str) -> bool:
        self.messages.append(text)
        return self.working


class FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.status_code = status

    def json(self) -> Any:
        return json.loads(self.text)


class FakeTransport:
    """Answers with the captured portal responses and notes what it was sent."""

    def __init__(
        self,
        *,
        weeks: dict[str, str] | None = None,
        claim: str = "claim_ok.json",
        pending: list[str] | None = None,
        release: str = "release_ok.json",
        bookable: set[str] | None = None,
        status: int = 200,
        vehicles_status: int | None = None,
        vehicles_body: str | None = None,
        offline: bool = False,
    ) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._weeks = weeks or {}
        self._claim = claim
        self._pending = list(pending or ["pending_ok.json"])
        self._release = release
        self._bookable = bookable or set()
        self._status = status
        self._vehicles_status = vehicles_status
        self._vehicles_body = vehicles_body
        self._offline = offline

    def post(self, url: str, data: Any = None, timeout: float | None = None) -> FakeResponse:
        path = urlsplit(url).path
        fields = {k: str(v) for k, v in (data or {}).items()}
        self.calls.append((path, fields))
        if self._offline:
            raise requests.ConnectionError("the router is rebooting")
        if self._status != 200:
            return FakeResponse("", self._status)
        if path.endswith("GetAvalablevehicleTypeDayWise"):
            if self._vehicles_status is not None:
                return FakeResponse(self._vehicles_body or "", self._vehicles_status)
            if self._vehicles_body is not None:
                return FakeResponse(self._vehicles_body)
            if fields.get("booking_date") in self._bookable:
                return FakeResponse('<select><option value="2">TESTPLATE</option></select>')
            return FakeResponse("0")
        if path.endswith("claimSpot"):
            return FakeResponse(fixture(self._claim))
        if path.endswith("getPendingClaimStatus"):
            name = self._pending.pop(0) if len(self._pending) > 1 else self._pending[0]
            # The capture is from 5 Oct; the real server answers about the date asked for.
            return FakeResponse(fixture(name).replace("2026-10-05", fields["date"]))
        if path.endswith("releaseAssignSpot"):
            return FakeResponse(fixture(self._release))
        if path.endswith("Claim_release"):
            return FakeResponse(
                fixture(self._weeks.get(fields.get("StartDate", ""), "week_full.json"))
            )
        raise AssertionError(f"unexpected path: {path}")

    def paths(self) -> list[str]:
        return [p for p, _ in self.calls]

    def body(self, suffix: str) -> dict[str, str]:
        for path, fields in self.calls:
            if path.endswith(suffix):
                return fields
        raise AssertionError(f"{suffix} was never called")
