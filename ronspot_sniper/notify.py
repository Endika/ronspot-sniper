"""Avisos por Slack, reutilizando el canal que ya usa el Pi."""

from __future__ import annotations

import logging
from typing import Protocol

import requests

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


SLACK_API = "https://slack.com/api/chat.postMessage"


class Slack:
    def __init__(
        self, token: str, channel: str, *, session: requests.Session | None = None
    ) -> None:
        self._token = token
        self._channel = channel
        self._http = session or requests.Session()

    def send(self, text: str) -> bool:
        if not self._token or not self._channel:
            log.warning("Slack sin configurar; el aviso se queda sin enviar: %s", text)
            return False
        try:
            response = self._http.post(
                SLACK_API,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"channel": self._channel, "text": text},
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            log.error("Slack no ha aceptado el aviso: %s", exc)
            return False
        if not payload.get("ok"):
            log.error("Slack ha respondido error: %s", payload.get("error"))
            return False
        return True


class Silent:
    """Para --dry-run: enseña el aviso por consola sin mandarlo."""

    def send(self, text: str) -> bool:
        print(f"[slack] {text}")
        return True
