"""Ronspot's JSON into domain values. The only place that knows their field names."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Mapping
from typing import Any

from ...domain import Booking, Day

log = logging.getLogger(__name__)


def to_int(value: Any) -> int:
    """Ronspot mixes `0`, `"0"` and `""` for the same idea."""
    try:
        return int(str(value).strip() or 0)
    except ValueError:
        return 0


def parse_day(raw: Mapping[str, Any]) -> Day | None:
    """One calendar day, or `None` if it is unreadable — a bad day must not kill a week."""
    try:
        date = dt.date.fromisoformat(str(raw["Full_Date"]))
    except (KeyError, ValueError):
        log.warning("unreadable calendar day, skipping it: %r", raw.get("Full_Date"))
        return None
    bay = str(raw.get("ParkingBayNumber") or "")
    return Day(
        date=date,
        free_bays=to_int(raw.get("AvailableParkingBay")),
        spot_id=to_int(raw.get("SpotID")),
        bay="" if bay == "0" else bay,
        blocked=to_int(raw.get("varIsBlocked")) == 1 or to_int(raw.get("varIsSemiBlocked")) == 1,
        calendar_says_free=to_int(raw.get("Spotavailable")) == 1,
    )


def parse_confirmation(payload: Mapping[str, Any], date: dt.date) -> Booking | None:
    """A firm booking out of the pending-claim answer, if there is one yet."""
    schedule = payload.get("Records", {}).get("Schedule", [])
    for row in schedule:
        if str(row.get("Full_Date")) != date.isoformat():
            continue
        if str(row.get("isClaimSuccessful")) == "1":
            return Booking(date, to_int(row.get("SpotID")), str(row.get("ParkingBayNumber") or ""))
    return None
