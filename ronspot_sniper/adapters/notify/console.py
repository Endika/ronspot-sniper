"""With no destination configured, alerts go to the console."""

from __future__ import annotations

from collections.abc import Mapping


class Console:
    """From cron this lands in the log, so nothing is lost: it just misses your phone."""

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Console:  # noqa: ARG003
        return cls()

    def send(self, text: str) -> bool:
        print(text)
        return True
