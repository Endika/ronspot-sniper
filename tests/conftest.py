"""Ningún test sale a internet.

Un test que llama a my.ronspot.ie de verdad es lento, frágil, y sobre este portal en
concreto puede acabar en una reserva rechazada y una notificación al móvil de alguien.
Ya pasó una vez, así que aquí se corta de raíz.
"""

import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    def prohibido(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("un test ha intentado salir a la red; usa tests/fake.py")

    monkeypatch.setattr(socket.socket, "connect", prohibido)
    monkeypatch.setattr(socket, "create_connection", prohibido)
