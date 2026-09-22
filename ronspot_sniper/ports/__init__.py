"""The two real boundaries: the booking service, and wherever alerts go.

The application layer talks only to these. Everything that knows about HTTP, Slack or
JSON files lives behind them, in `adapters/`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain import Booking, Week


class GatewayError(RuntimeError):
    """Base for every way the booking service can refuse to be useful."""


class Unreachable(GatewayError):
    """No answer, or the service is broken (5xx).

    The router reboots at 04:00 and takes ~2 min, so this happens daily and is not an
    error: the tick is skipped silently and the next one tries again.
    """


class RateLimited(GatewayError):
    def __init__(self, status: int) -> None:
        super().__init__(f"service answered {status}")
        self.status = status


class SessionExpired(GatewayError):
    """The credentials no longer work and a human must re-seed them."""


@dataclass(frozen=True)
class ClaimResult:
    accepted: bool
    message: str


@runtime_checkable
class BookingGateway(Protocol):
    """A parking service we can read and book against."""

    def week(self, start: dt.date) -> Week:
        """The seven days starting on `start`."""
        ...

    def bookable(self, date: dt.date) -> bool:
        """Whether a spot can actually be taken on `date`, right now."""
        ...

    def claim(self, date: dt.date) -> ClaimResult:
        """Ask for a spot. Acceptance does not mean the booking is firm."""
        ...

    def confirm(self, date: dt.date, *, tries: int = 8, gap: float = 1.5) -> Booking | None:
        """Wait for the claim to become a real booking, or give up."""
        ...

    def release(self, booking: Booking) -> bool:
        """Give a booking back."""
        ...


@runtime_checkable
class Notifier(Protocol):
    def send(self, text: str) -> bool:
        """Deliver `text`. Returns whether it actually got through."""
        ...


__all__ = [
    "BookingGateway",
    "ClaimResult",
    "GatewayError",
    "Notifier",
    "RateLimited",
    "SessionExpired",
    "Unreachable",
]
