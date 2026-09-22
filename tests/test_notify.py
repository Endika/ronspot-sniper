import tomllib
from typing import Any

import pytest

from ronspot_sniper.config import _notify
from ronspot_sniper.notify import (
    ADAPTADORES,
    Console,
    Discord,
    Notifier,
    Slack,
    UnknownNotifier,
    build,
)


class FakeHTTP:
    """Un `requests.Session` de mentira: apunta lo que se le manda y devuelve lo pedido."""

    def __init__(
        self,
        status: int = 200,
        payload: dict[str, Any] | None = None,
        boom: Exception | None = None,
    ) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else {"ok": True}
        self._boom = boom
        self.posts: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> "FakeHTTP":
        if self._boom is not None:
            raise self._boom
        self.posts.append((url, kwargs.get("json", {})))
        return self

    def json(self) -> dict[str, Any]:
        return self._payload


def test_every_adapter_satisfies_the_port():
    for nombre, factory in ADAPTADORES.items():
        hecho = factory({"token": "t", "channel": "c", "webhook": "https://x/y"})
        assert isinstance(hecho, Notifier), nombre


def test_discord_posts_the_text_to_the_webhook():
    http = FakeHTTP()
    discord = Discord("https://discord.com/api/webhooks/abc", session=http)  # type: ignore[arg-type]

    assert discord.send("plaza cogida")
    assert http.posts == [("https://discord.com/api/webhooks/abc", {"content": "plaza cogida"})]


def test_discord_reports_failure_instead_of_raising():
    caido = Discord("https://x/y", session=FakeHTTP(status=404))  # type: ignore[arg-type]
    roto = Discord("https://x/y", session=FakeHTTP(boom=OSError("sin red")))  # type: ignore[arg-type]

    assert not caido.send("hola")
    with pytest.raises(OSError):
        roto.send("hola")


def test_slack_reads_the_ok_field_not_just_the_status():
    bueno = Slack("t", "c", session=FakeHTTP(payload={"ok": True}))  # type: ignore[arg-type]
    malo = Slack("t", "c", session=FakeHTTP(payload={"ok": False, "error": "channel_not_found"}))  # type: ignore[arg-type]

    assert bueno.send("hola")
    assert not malo.send("hola")


def test_an_unknown_adapter_says_which_ones_exist():
    with pytest.raises(UnknownNotifier, match="discord"):
        build("telegram", {})


def test_an_adapter_without_its_options_falls_back_to_the_console():
    """Un aviso mal configurado no debe impedirte cazar la plaza."""
    assert isinstance(build("slack", {}), Console)
    assert isinstance(build("discord", {"webhook": ""}), Console)


def test_the_config_picks_the_adapter_and_its_own_section():
    raw = tomllib.loads("""
        [notify]
        kind = "discord"
        [notify.discord]
        webhook = "https://discord.com/api/webhooks/abc"
        [notify.slack]
        token = "no-es-este"
    """)

    assert _notify(raw) == ("discord", {"webhook": "https://discord.com/api/webhooks/abc"})


def test_an_old_config_with_only_a_slack_section_still_works():
    raw = tomllib.loads('[slack]\ntoken = "xoxb-x"\nchannel = "C123"')

    assert _notify(raw) == ("slack", {"token": "xoxb-x", "channel": "C123"})


def test_no_notify_section_at_all_means_console():
    assert _notify({}) == ("console", {})
