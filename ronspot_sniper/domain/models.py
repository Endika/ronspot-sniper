"""Immutable values the rest of the program reasons about."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Day:
    """One day of the parking calendar, as the domain sees it."""

    date: dt.date
    free_bays: int
    spot_id: int
    bay: str
    blocked: bool
    calendar_says_free: bool
    """What Ronspot's `Spotavailable` claims. Measured: it does not match reality — it
    reads 1 on full days and 0 on bookable ones. Informational only; whether a spot can
    actually be taken is answered by the booking gateway."""

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


@dataclass(frozen=True)
class SniperConfig:
    """What the policy needs to decide. Deliberately smaller than the file config:
    the domain has no business knowing about tokens, paths or base URLs."""

    weekdays: frozenset[int]
    horizon_days: int
    resync_seconds: int = 1800
    confirm_tries: int = 8
    confirm_gap: float = 1.5
