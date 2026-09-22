"""No test reaches the internet.

A test that really calls my.ronspot.ie is slow, flaky, and on this portal in particular
can end in a rejected booking and a notification on somebody's phone. It happened once,
so it is cut off at the root here.
"""

import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("a test tried to reach the network; use tests/fakes.py")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
