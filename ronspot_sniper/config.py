"""Reading the TOML file into the pieces each layer needs.

The domain gets a `SniperConfig` with the decisions it makes; the adapters get their own
credentials and paths. Nothing downstream re-reads the file.
"""

from __future__ import annotations

import datetime as dt
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain import SniperConfig

DEFAULT_CONFIG = Path("~/.ronspot/config.toml").expanduser()


@dataclass(frozen=True)
class GatewaySettings:
    guid: str
    zone_id: int
    base_url: str
    vehicle_type_id: int
    vehicle_fuel_id: int
    session_path: Path


@dataclass(frozen=True)
class Settings:
    sniper: SniperConfig
    gateway: GatewaySettings
    notify_kind: str
    notify_options: dict[str, str]
    state_path: Path
    give_up_at: dt.time | None
    local_tz: str

    @classmethod
    def load(cls, path: Path) -> Settings:
        raw = tomllib.loads(path.read_text())
        ronspot, sniper = raw["ronspot"], raw.get("sniper", {})
        paths = raw.get("paths", {})
        root = path.parent
        kind, options = _notify(raw)
        return cls(
            sniper=SniperConfig(
                weekdays=frozenset(sniper.get("weekdays", [1, 3])),
                horizon_days=int(sniper.get("horizon_days", 14)),
                resync_seconds=int(sniper.get("resync_minutes", 30)) * 60,
                confirm_tries=int(sniper.get("confirm_tries", 8)),
                confirm_gap=float(sniper.get("confirm_gap", 1.5)),
            ),
            gateway=GatewaySettings(
                guid=ronspot["guid"],
                zone_id=int(ronspot["zone_id"]),
                base_url=ronspot.get("base_url", "https://my.ronspot.ie"),
                vehicle_type_id=int(ronspot.get("vehicle_type_id", 2)),
                vehicle_fuel_id=int(ronspot.get("vehicle_fuel_id", 2)),
                session_path=Path(paths.get("session", root / "session.json")).expanduser(),
            ),
            notify_kind=kind,
            notify_options=options,
            state_path=Path(paths.get("state", root / "state.json")).expanduser(),
            give_up_at=_parse_time(sniper.get("giveup_time", "09:30")),
            local_tz=str(sniper.get("local_tz", "Europe/Madrid")),
        )


def _notify(raw: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """`[notify] kind = "discord"` plus its own section. A bare `[slack]` still works:
    that is how it looked before the destination was configurable."""
    block = raw.get("notify")
    if isinstance(block, dict):
        kind = str(block.get("kind", "console"))
        own = block.get(kind)
        options = {k: str(v) for k, v in own.items()} if isinstance(own, dict) else {}
        return kind, options
    legacy = raw.get("slack")
    if isinstance(legacy, dict) and legacy.get("token"):
        return "slack", {k: str(v) for k, v in legacy.items()}
    return "console", {}


def _parse_time(raw: object) -> dt.time | None:
    """Local time after which the current day stops being worth chasing."""
    if raw in (None, "", False):
        return None
    return dt.time.fromisoformat(str(raw))


def load_cookies(path: Path) -> dict[str, str]:
    """Reads the storage state left by `tools/capture.mjs` and picks Ronspot's cookies."""
    raw = json.loads(path.read_text())
    cookies = raw["cookies"] if isinstance(raw, dict) and "cookies" in raw else raw
    return {c["name"]: c["value"] for c in cookies if "ronspot" in c.get("domain", "")}
