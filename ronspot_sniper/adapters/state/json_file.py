"""The state as a JSON file, written atomically and mode 600."""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ...domain.state import State


def load_state(path: Path) -> State:
    """Never raises: a corrupt file must not stop a cron tick that runs every minute."""
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return State()
    if not isinstance(raw, dict):
        return State()
    fresh = State()
    for key, value in raw.items():
        current = getattr(fresh, key, None)
        if key not in State.__dataclass_fields__ or type(value) is not type(current):
            continue
        setattr(fresh, key, value)
    try:
        fresh.covered_dates()
        {dt.date.fromisoformat(d) for d in fresh.rejected}
        {dt.date.fromisoformat(d) for d in fresh.confirmed_at}
    except (TypeError, ValueError):
        return State()
    return fresh


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(asdict(state), stream, indent=1)
        Path(tmp).replace(path)
        path.chmod(0o600)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
