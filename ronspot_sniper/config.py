"""Configuración y cookie de sesión, ambas fuera del repo."""

from __future__ import annotations

import datetime as dt
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("~/ronspot/config.toml").expanduser()


def _notify(raw: dict[str, object]) -> tuple[str, dict[str, str]]:
    """`[notify] kind = "discord"` más su sección propia. Un `[slack]` suelto sigue
    valiendo: es como estaba antes de que esto fuera configurable."""
    bloque = raw.get("notify")
    if isinstance(bloque, dict):
        kind = str(bloque.get("kind", "console"))
        propias = bloque.get(kind)
        options = {k: str(v) for k, v in propias.items()} if isinstance(propias, dict) else {}
        return kind, options
    legado = raw.get("slack")
    if isinstance(legado, dict) and legado.get("token"):
        return "slack", {k: str(v) for k, v in legado.items()}
    return "console", {}


def _parse_time(raw: object) -> dt.time | None:
    """Hora de Madrid a partir de la cual el día en curso deja de interesar."""
    if raw in (None, "", False):
        return None
    return dt.time.fromisoformat(str(raw))


@dataclass(frozen=True)
class Config:
    guid: str
    zone_id: int
    base_url: str
    vehicle_type_id: int
    vehicle_fuel_id: int
    weekdays: tuple[int, ...]
    horizon_days: int
    giveup_time: dt.time | None
    local_tz: str
    confirm_tries: int
    confirm_gap: float
    resync_seconds: int
    notify_kind: str
    notify_options: dict[str, str]
    session_path: Path
    state_path: Path

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = tomllib.loads(path.read_text())
        ronspot, sniper = raw["ronspot"], raw.get("sniper", {})
        paths = raw.get("paths", {})
        kind, options = _notify(raw)
        root = path.parent
        return cls(
            guid=ronspot["guid"],
            zone_id=int(ronspot["zone_id"]),
            base_url=ronspot.get("base_url", "https://my.ronspot.ie"),
            vehicle_type_id=int(ronspot.get("vehicle_type_id", 2)),
            vehicle_fuel_id=int(ronspot.get("vehicle_fuel_id", 2)),
            weekdays=tuple(sniper.get("weekdays", [1, 3])),
            horizon_days=int(sniper.get("horizon_days", 14)),
            giveup_time=_parse_time(sniper.get("giveup_time", "09:30")),
            local_tz=str(sniper.get("local_tz", "Europe/Madrid")),
            confirm_tries=int(sniper.get("confirm_tries", 8)),
            confirm_gap=float(sniper.get("confirm_gap", 1.5)),
            resync_seconds=int(sniper.get("resync_minutes", 30)) * 60,
            notify_kind=kind,
            notify_options=options,
            session_path=Path(paths.get("session", root / "session.json")).expanduser(),
            state_path=Path(paths.get("state", root / "state.json")).expanduser(),
        )


def load_cookies(path: Path) -> dict[str, str]:
    """Lee el storage state que deja tools/capture.mjs y saca las cookies de Ronspot."""
    raw = json.loads(path.read_text())
    cookies = raw["cookies"] if isinstance(raw, dict) and "cookies" in raw else raw
    return {c["name"]: c["value"] for c in cookies if "ronspot" in c.get("domain", "")}
