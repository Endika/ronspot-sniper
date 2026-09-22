"""Sin destino configurado, los avisos salen por consola."""

from __future__ import annotations

from collections.abc import Mapping


class Console:
    """Desde cron esto acaba en el log, así que no se pierde: solo no te llega al móvil."""

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Console:  # noqa: ARG003
        return cls()

    def send(self, text: str) -> bool:
        print(text)
        return True
