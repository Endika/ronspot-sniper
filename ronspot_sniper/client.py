"""Cliente del portal de empleado de Ronspot (my.ronspot.ie)."""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import requests

log = logging.getLogger(__name__)

CALENDAR = "/member/Claim_release"
CLAIM = "/member/Claim_release/claimSpot"
PENDING = "/index.php/member/claim_release/getPendingClaimStatus"
RELEASE = "/member/Claim_release/releaseAssignSpot"
VEHICLES = "/member/Claim_release/GetAvalablevehicleTypeDayWise"


class SessionExpired(RuntimeError):
    """Ronspot ha devuelto el login en vez de datos: hay que re-sembrar la cookie."""


class Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...

    def raise_for_status(self) -> None: ...


class Transport(Protocol):
    """Lo único que el cliente necesita de `requests.Session`; los tests inyectan un doble."""

    def post(
        self,
        url: str,
        data: Mapping[str, Any] | None = ...,
        *,
        timeout: float | None = ...,
    ) -> Response: ...


class Unreachable(RuntimeError):
    """No se puede hablar con Ronspot ahora mismo: sin red, o el portal devuelve 5xx.

    El router se reinicia a las 04:00 y tarda ~2 min, así que esto pasa a diario y no es
    un error: el tic se salta en silencio y el siguiente lo intenta otra vez."""


class RateLimited(RuntimeError):
    def __init__(self, status: int) -> None:
        super().__init__(f"Ronspot respondió {status}")
        self.status = status


def _int(value: Any) -> int:
    try:
        return int(str(value).strip() or 0)
    except ValueError:
        return 0


@dataclass(frozen=True)
class Day:
    date: dt.date
    free_bays: int
    spot_id: int
    bay: str
    blocked: bool
    calendar_says_free: bool
    """Lo que anuncia `Spotavailable`. Medido: no se corresponde con la realidad — sale 1
    en días llenos y 0 en días reservables. Solo vale para informar; quien decide es
    `RonspotClient.bookable()`."""

    @property
    def mine(self) -> bool:
        return self.spot_id != 0

    @property
    def worth_trying(self) -> bool:
        return not self.mine and not self.blocked


@dataclass(frozen=True)
class Week:
    start: dt.date
    days: tuple[Day, ...]


@dataclass(frozen=True)
class Booking:
    date: dt.date
    spot_id: int
    bay: str


def _parse_day(raw: Mapping[str, Any]) -> Day | None:
    try:
        date = dt.date.fromisoformat(str(raw["Full_Date"]))
    except (KeyError, ValueError):
        log.warning("día del calendario ilegible, se ignora: %r", raw.get("Full_Date"))
        return None
    bay = str(raw.get("ParkingBayNumber") or "")
    return Day(
        date=date,
        free_bays=_int(raw.get("AvailableParkingBay")),
        spot_id=_int(raw.get("SpotID")),
        bay="" if bay == "0" else bay,
        blocked=_int(raw.get("varIsBlocked")) == 1 or _int(raw.get("varIsSemiBlocked")) == 1,
        calendar_says_free=_int(raw.get("Spotavailable")) == 1,
    )


class RonspotClient:
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
    ) -> None:
        self.guid = guid
        self.zone_id = zone_id
        self.base_url = base_url.rstrip("/")
        self.vehicle_type_id = vehicle_type_id
        self.vehicle_fuel_id = vehicle_fuel_id
        if transport is None:
            session: requests.Session = requests.Session()
            session.headers.update(
                {
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) ronspot-sniper",
                    "Referer": f"{self.base_url}{CALENDAR}",
                }
            )
            for name, value in cookies.items():
                session.cookies.set(name, value, domain="my.ronspot.ie")
            self._http: Transport = session
        else:
            self._http = transport
        self._token = ""

    def _fetch(self, path: str, data: Mapping[str, Any]) -> Response:
        try:
            response = self._http.post(f"{self.base_url}{path}", data=data, timeout=20)
        except requests.RequestException as exc:
            raise Unreachable(f"{path}: {exc}") from exc
        if response.status_code in (401, 403, 429):
            raise RateLimited(response.status_code)
        if response.status_code >= 400:
            log.warning("Ronspot ha respondido %s en %s", response.status_code, path)
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
            raise SessionExpired(f"{path}: respuesta no es JSON") from exc
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
            parsed for raw in payload.get("future_dates", []) if (parsed := _parse_day(raw))
        )
        return Week(start, days)

    def bookable(self, date: dt.date) -> bool:
        """La señal honesta: Ronspot solo ofrece el desplegable del coche si de verdad
        queda plaza para ti. `Spotavailable` del calendario se queda en 1 aunque no haya."""
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

    def claim(self, date: dt.date) -> tuple[bool, str]:
        """Pide la plaza. Devuelve (aceptada, mensaje); la reserva aún no es firme."""
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
        ok = _int(payload.get("ResponseCode")) == 200
        return ok, str(payload.get("ErrorMessage") or payload.get("Message") or "")

    def confirm(
        self,
        date: dt.date,
        *,
        tries: int = 8,
        gap: float = 1.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> Booking | None:
        """Sondea la cola de Ronspot hasta que la reserva pasa de 'In Process' a firme."""
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
            schedule: Iterable[Mapping[str, Any]] = payload.get("Records", {}).get("Schedule", [])
            for row in schedule:
                if str(row.get("Full_Date")) != date.isoformat():
                    continue
                if str(row.get("isClaimSuccessful")) == "1":
                    bay = str(row.get("ParkingBayNumber") or "")
                    return Booking(date, _int(row.get("SpotID")), bay)
            if attempt < tries - 1:
                sleep(gap)
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
        return _int(payload.get("ResponseCode")) == 200
