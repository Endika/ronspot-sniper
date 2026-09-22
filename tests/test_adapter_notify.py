import tomllib
from typing import Any

import pytest

from ronspot_sniper.adapters.notify import (
    ADAPTERS,
    Console,
    Discord,
    Slack,
    UnknownNotifier,
    build,
)
from ronspot_sniper.config import _notify
from ronspot_sniper.ports import Notifier


class FakeHTTP:
    """A fake `requests.Session`: notes what it is sent, returns what it was told to."""

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
    for name, factory in ADAPTERS.items():
        made = factory({"token": "t", "channel": "c", "webhook": "https://x/y"})
        assert isinstance(made, Notifier), name


def test_discord_posts_the_text_to_the_webhook():
    http = FakeHTTP()
    discord = Discord("https://discord.com/api/webhooks/abc", session=http)

    assert discord.send("spot booked")
    assert http.posts == [("https://discord.com/api/webhooks/abc", {"content": "spot booked"})]


def test_discord_reports_failure_instead_of_raising():
    assert not Discord("https://x/y", session=FakeHTTP(status=404)).send("hi")


def test_slack_reads_the_ok_field_not_just_the_status():
    good = Slack("t", "c", session=FakeHTTP(payload={"ok": True}))
    bad = Slack("t", "c", session=FakeHTTP(payload={"ok": False, "error": "channel_not_found"}))

    assert good.send("hi")
    assert not bad.send("hi")


def test_an_unknown_adapter_says_which_ones_exist():
    with pytest.raises(UnknownNotifier, match="discord"):
        build("telegram", {})


def test_an_adapter_without_its_options_falls_back_to_the_console():
    """A misconfigured notifier must never stop you getting the spot."""
    assert isinstance(build("slack", {}), Console)
    assert isinstance(build("discord", {"webhook": ""}), Console)


def test_the_console_adapter_prints(capsys):
    assert build("console", {}).send("hello")
    assert "hello" in capsys.readouterr().out


def test_the_config_picks_the_adapter_and_its_own_section():
    raw = tomllib.loads("""
        [notify]
        kind = "discord"
        [notify.discord]
        webhook = "https://discord.com/api/webhooks/abc"
        [notify.slack]
        token = "not-this-one"
    """)

    assert _notify(raw) == ("discord", {"webhook": "https://discord.com/api/webhooks/abc"})


def test_an_old_config_with_only_a_slack_section_still_works():
    raw = tomllib.loads('[slack]\ntoken = "xoxb-x"\nchannel = "C123"')

    assert _notify(raw) == ("slack", {"token": "xoxb-x", "channel": "C123"})


def test_no_notify_section_at_all_means_console():
    assert _notify({}) == ("console", {})
