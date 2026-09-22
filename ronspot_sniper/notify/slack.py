"""Avisos por Slack con un bot token (`chat:write`)."""

from __future__ import annotations

import logging
from collections.abc import Mapping

import requests

log = logging.getLogger(__name__)
API = "https://slack.com/api/chat.postMessage"


class Slack:
    def __init__(self, token: str, channel: str, *, session: requests.Session | None = None):
        self._token = token
        self._channel = channel
        self._http = session or requests.Session()

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Slack | None:
        token, channel = options.get("token", ""), options.get("channel", "")
        return cls(token, channel) if token and channel else None

    def send(self, text: str) -> bool:
        try:
            response = self._http.post(
                API,
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
