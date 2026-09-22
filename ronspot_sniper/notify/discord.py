"""Avisos por Discord con un webhook de canal.

Se saca en Discord con: Editar canal > Integraciones > Webhooks > Nuevo webhook.
No hace falta bot ni permisos: la URL del webhook es todo.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import requests

log = logging.getLogger(__name__)


class Discord:
    def __init__(self, webhook: str, *, session: requests.Session | None = None):
        self._webhook = webhook
        self._http = session or requests.Session()

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Discord | None:
        webhook = options.get("webhook", "")
        return cls(webhook) if webhook else None

    def send(self, text: str) -> bool:
        try:
            response = self._http.post(self._webhook, json={"content": text}, timeout=15)
        except requests.RequestException as exc:
            log.error("Discord no ha aceptado el aviso: %s", exc)
            return False
        if response.status_code >= 400:
            log.error("Discord ha respondido %s", response.status_code)
            return False
        return True
