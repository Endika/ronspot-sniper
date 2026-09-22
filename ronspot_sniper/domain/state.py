"""What the sniper remembers between ticks, and the rules over it. No I/O."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field

BASE_BACKOFF = 300.0
MAX_BACKOFF = 7200.0


@dataclass
class State:
    blocked_until: float = 0.0
    backoff_level: int = 0
    session_alert_sent: bool = False
    covered: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)
    confirmed_at: dict[str, float] = field(default_factory=dict)
    last_sweep: float = 0.0

    def blocked(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.blocked_until

    def penalise(self, now: float | None = None) -> float:
        """Back off further each time, up to two hours."""
        now = now if now is not None else time.time()
        delay: float = min(BASE_BACKOFF * (2**self.backoff_level), MAX_BACKOFF)
        self.backoff_level += 1
        self.blocked_until = now + delay
        return delay

    def relax(self) -> None:
        self.backoff_level = 0
        self.blocked_until = 0.0

    def covered_dates(self) -> set[dt.date]:
        return {dt.date.fromisoformat(d) for d in self.covered}

    def forget_past(self, today: dt.date) -> None:
        """Drop yesterday, so the file never grows without bound."""
        self.covered = {
            d: bay for d, bay in self.covered.items() if dt.date.fromisoformat(d) >= today
        }
        self.rejected = {
            d: n for d, n in self.rejected.items() if dt.date.fromisoformat(d) >= today
        }
        self.confirmed_at = {
            d: t for d, t in self.confirmed_at.items() if dt.date.fromisoformat(d) >= today
        }
