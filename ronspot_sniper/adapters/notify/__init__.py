"""Notification adapters and the registry that picks one from config.

Adding a destination means one module here plus one line in `ADAPTERS`; nothing else in
the program changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ...ports import Notifier
from .console import Console
from .discord import Discord
from .slack import Slack

Factory = Callable[[Mapping[str, str]], "Notifier | None"]

ADAPTERS: dict[str, Factory] = {
    "console": Console.from_options,
    "slack": Slack.from_options,
    "discord": Discord.from_options,
}


class UnknownNotifier(ValueError):
    pass


def build(kind: str, options: Mapping[str, str]) -> Notifier:
    """Create the adapter the config asks for; fall back to the console if it lacks data.

    Falling back rather than raising is deliberate: this runs from cron every minute, and
    a misconfigured notifier must never stop you getting the spot.
    """
    if kind not in ADAPTERS:
        raise UnknownNotifier(f"{kind!r} does not exist; available: {', '.join(sorted(ADAPTERS))}")
    made = ADAPTERS[kind](options)
    return made if made is not None else Console()


__all__ = ["ADAPTERS", "Console", "Discord", "Factory", "Slack", "UnknownNotifier", "build"]
