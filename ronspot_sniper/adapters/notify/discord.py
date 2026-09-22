"""Discord alerts through a channel webhook.

Get one in Discord with: Edit channel > Integrations > Webhooks > New webhook.
No bot and no permissions needed: the webhook URL is everything.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import requests

from ._http import HttpClient

log = logging.getLogger(__name__)


class Discord:
    def __init__(self, webhook: str, *, session: HttpClient | None = None):
        self._webhook = webhook
        self._http: HttpClient = session or requests.Session()

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Discord | None:
        webhook = options.get("webhook", "")
        return cls(webhook) if webhook else None

    def send(self, text: str) -> bool:
        try:
            response = self._http.post(self._webhook, json={"content": text}, timeout=15)
        except requests.RequestException as exc:
            log.error("Discord did not accept the alert: %s", exc)
            return False
        if response.status_code >= 400:
            log.error("Discord answered %s", response.status_code)
            return False
        return True
