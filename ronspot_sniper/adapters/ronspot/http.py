"""Talks to my.ronspot.ie exactly the way the browser does."""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import requests

from ...domain import Booking, Week
from ...ports import ClaimResult, RateLimited, SessionExpired, Unreachable
from .parsing import parse_confirmation, parse_day, to_int

log = logging.getLogger(__name__)

CALENDAR = "/member/Claim_release"
CLAIM = "/member/Claim_release/claimSpot"
PENDING = "/index.php/member/claim_release/getPendingClaimStatus"
RELEASE = "/member/Claim_release/releaseAssignSpot"
VEHICLES = "/member/Claim_release/GetAvalablevehicleTypeDayWise"


class Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


class Transport(Protocol):
    """All this adapter needs from `requests.Session`; tests inject a stand-in."""

    def post(
        self,
        url: str,
        data: Mapping[str, Any] | None = ...,
        *,
        timeout: float | None = ...,
    ) -> Response: ...


def _session(base_url: str, cookies: Mapping[str, str]) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) ronspot-sniper",
            "Referer": f"{base_url}{CALENDAR}",
        }
    )
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="my.ronspot.ie")
    return session


class RonspotGateway:
    """Implements `ports.BookingGateway`."""

    def __init__(
        self,
        cookies: Mapping[str, str],
        guid: str,
        zone_id: int,
        *,
        base_url: str = "https://my.ronspot.ie",
        vehicle_type_id: int = 2,
        vehicle_fuel_id: int = 2,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.guid = guid
        self.zone_id = zone_id
        self.base_url = base_url.rstrip("/")
        self.vehicle_type_id = vehicle_type_id
        self.vehicle_fuel_id = vehicle_fuel_id
        self._http: Transport = transport or _session(self.base_url, cookies)
        self._sleep = sleep
        self._token = ""

    def _fetch(self, path: str, data: Mapping[str, Any]) -> Response:
        try:
            response = self._http.post(f"{self.base_url}{path}", data=data, timeout=20)
        except requests.RequestException as exc:
            raise Unreachable(f"{path}: {exc}") from exc
        if response.status_code in (401, 403, 429):
            raise RateLimited(response.status_code)
        if response.status_code >= 400:
            log.warning("Ronspot answered %s on %s", response.status_code, path)
            raise Unreachable(f"{path}: HTTP {response.status_code}")
        body = response.text
        if body.lstrip().startswith("<!") or "login-form" in body:
            raise SessionExpired(path)
        return response

    def _post(self, path: str, data: Mapping[str, Any]) -> dict[str, Any]:
        response = self._fetch(path, data)
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise SessionExpired(f"{path}: answer is not JSON") from exc
        # Ronspot rotates its CSRF token on every mutation; the next call needs the fresh one.
        token = payload.get("ronspot_token")
        if token:
            self._token = str(token)
        return payload

    def week(self, start: dt.date) -> Week:
        payload = self._post(
            CALENDAR,
            {
                "car_park_id": self.zone_id,
                "CollegesGuID": self.guid,
                "StartDate": start.isoformat(),
                "refreshicon": "1",
                "filterByJson": "",
            },
        )
        days = tuple(
            parsed for raw in payload.get("future_dates", []) if (parsed := parse_day(raw))
        )
        return Week(start, days)

    def bookable(self, date: dt.date) -> bool:
        """Ronspot only offers the vehicle dropdown when a spot really is yours to take.
        The calendar's `Spotavailable` stays at 1 even when there is none."""
        response = self._fetch(
            VEHICLES,
            {
                "booking_date": date.isoformat(),
                "GuId": self.guid,
                "car_park_id": self.zone_id,
                "filterByJson": "",
                "liftSpotAvailable": 1,
                "call_from": "calendar",
            },
        )
        return "<option" in response.text

    def claim(self, date: dt.date) -> ClaimResult:
        if not self._token:
            self.week(date - dt.timedelta(days=date.weekday()))
        payload = self._post(
            CLAIM,
            {
                "booking_date": date.isoformat(),
                "CollegesGuID": self.guid,
                "day_no": date.day,
                "car_park_id": self.zone_id,
                "VehicleTypeId": self.vehicle_type_id,
                "VehicleFuelId": self.vehicle_fuel_id,
                "VehicleAccessibleId": "",
                "VehicleShareableId": "",
                "ronspot_token": self._token,
            },
        )
        return ClaimResult(
            accepted=to_int(payload.get("ResponseCode")) == 200,
            message=str(payload.get("ErrorMessage") or payload.get("Message") or ""),
        )

    def confirm(self, date: dt.date, *, tries: int = 8, gap: float = 1.5) -> Booking | None:
        """Ronspot queues the claim and answers 'In Process'; only this says it is real."""
        for attempt in range(tries):
            payload = self._post(
                PENDING,
                {
                    "date": date.isoformat(),
                    "GuId": self.guid,
                    "ZoneID": self.zone_id,
                    "isGuest": "0",
                    "Type": "1",
                },
            )
            booking = parse_confirmation(payload, date)
            if booking is not None:
                return booking
            if attempt < tries - 1:
                self._sleep(gap)
        return None

    def release(self, booking: Booking) -> bool:
        payload = self._post(
            RELEASE,
            {
                "release_date": booking.date.isoformat(),
                "CollegesGuID": self.guid,
                "day_no": booking.date.day,
                "spot": booking.bay,
                "SpotID": booking.spot_id,
                "car_park_id": self.zone_id,
                "ronspot_token": self._token,
            },
        )
        return to_int(payload.get("ResponseCode")) == 200
