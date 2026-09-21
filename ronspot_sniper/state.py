"""Estado entre tics de cron: backoff, avisos ya enviados y días ya cazados."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

BASE_BACKOFF = 300.0
MAX_BACKOFF = 7200.0


@dataclass
class State:
    blocked_until: float = 0.0
    backoff_level: int = 0
    session_alert_sent: bool = False
    covered: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)
    last_sweep: float = 0.0

    @classmethod
    def load(cls, path: Path) -> State:
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            return cls()
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(asdict(self), handle, indent=1)
            Path(tmp).replace(path)
            path.chmod(0o600)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def blocked(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.blocked_until

    def penalise(self, now: float | None = None) -> float:
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
        self.covered = {
            d: bay for d, bay in self.covered.items() if dt.date.fromisoformat(d) >= today
        }
        self.rejected = {
            d: n for d, n in self.rejected.items() if dt.date.fromisoformat(d) >= today
        }
