"""El puerto de avisos y su registro de adaptadores.

El resto del programa solo conoce `Notifier.send(texto)`. Para añadir un destino nuevo
basta con un módulo aquí dentro que registre su clase; no hay que tocar nada más.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, runtime_checkable

from .console import Console
from .discord import Discord
from .slack import Slack


@runtime_checkable
class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


Factory = Callable[[Mapping[str, str]], "Notifier | None"]

ADAPTADORES: dict[str, Factory] = {
    "console": Console.from_options,
    "slack": Slack.from_options,
    "discord": Discord.from_options,
}


class UnknownNotifier(ValueError):
    pass


def build(kind: str, options: Mapping[str, str]) -> Notifier:
    """Crea el adaptador que diga el config. Si le faltan datos, cae a consola.

    Caer a consola y no reventar es deliberado: esto corre desde cron cada minuto, y un
    aviso mal configurado no debe impedirte cazar la plaza.
    """
    if kind not in ADAPTADORES:
        raise UnknownNotifier(f"{kind!r} no existe; hay: {', '.join(sorted(ADAPTADORES))}")
    hecho = ADAPTADORES[kind](options)
    return hecho if hecho is not None else Console()


__all__ = [
    "ADAPTADORES",
    "Console",
    "Discord",
    "Factory",
    "Notifier",
    "Slack",
    "UnknownNotifier",
    "build",
]
