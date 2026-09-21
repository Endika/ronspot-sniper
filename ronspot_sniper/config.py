"""Configuración y cookie de sesión, ambas fuera del repo."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("~/ronspot/config.toml").expanduser()


@dataclass(frozen=True)
class Config:
    guid: str
    zone_id: int
    base_url: str
    vehicle_type_id: int
    vehicle_fuel_id: int
    weekdays: tuple[int, ...]
    horizon_days: int
    confirm_tries: int
    confirm_gap: float
    resync_seconds: int
    slack_token: str
    slack_channel: str
    session_path: Path
    state_path: Path

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = tomllib.loads(path.read_text())
        ronspot, sniper = raw["ronspot"], raw.get("sniper", {})
        slack, paths = raw.get("slack", {}), raw.get("paths", {})
        root = path.parent
        return cls(
            guid=ronspot["guid"],
            zone_id=int(ronspot["zone_id"]),
            base_url=ronspot.get("base_url", "https://my.ronspot.ie"),
            vehicle_type_id=int(ronspot.get("vehicle_type_id", 2)),
            vehicle_fuel_id=int(ronspot.get("vehicle_fuel_id", 2)),
            weekdays=tuple(sniper.get("weekdays", [1, 3])),
            horizon_days=int(sniper.get("horizon_days", 14)),
            confirm_tries=int(sniper.get("confirm_tries", 8)),
            confirm_gap=float(sniper.get("confirm_gap", 1.5)),
            resync_seconds=int(sniper.get("resync_minutes", 30)) * 60,
            slack_token=slack.get("token", ""),
            slack_channel=slack.get("channel", ""),
            session_path=Path(paths.get("session", root / "session.json")).expanduser(),
            state_path=Path(paths.get("state", root / "state.json")).expanduser(),
        )


def load_cookies(path: Path) -> dict[str, str]:
    """Lee el storage state que deja tools/capture.mjs y saca las cookies de Ronspot."""
    raw = json.loads(path.read_text())
    cookies = raw["cookies"] if isinstance(raw, dict) and "cookies" in raw else raw
    return {c["name"]: c["value"] for c in cookies if "ronspot" in c.get("domain", "")}
