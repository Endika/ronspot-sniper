"""Turning what happened into the words a human reads. No markup tied to one chat app."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from ..domain import Booking, Day
from ..domain.state import State

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def pretty_date(date: dt.date) -> str:
    return f"{DAY_NAMES[date.weekday()]} {date.day:02d}/{date.month:02d}"


def _bay(bay: str) -> str:
    return bay or "no number"


def spots_taken(bookings: Sequence[Booking]) -> str:
    """One message however many spots were won; one per booking would be a pager storm."""
    if len(bookings) == 1:
        one = bookings[0]
        return f":car: Spot booked for {pretty_date(one.date)} — {_bay(one.bay)}"
    lines = "\n".join(f"• {pretty_date(b.date)} — {_bay(b.bay)}" for b in bookings)
    return f":car: {len(bookings)} spots booked:\n{lines}"


SESSION_EXPIRED = (
    ":lock: Ronspot: the session has expired and the sniper is blind. "
    "Re-seed it with `node tools/capture.mjs`."
)


def daily_summary(
    mine: Sequence[Day],
    pending: Sequence[dt.date],
    state: State,
    *,
    today: dt.date,
    give_up_at: dt.time | None,
    include_today: bool,
    stopped: str = "",
) -> str:
    """The daily report. It covers the case that produces no message: winning nothing."""
    if stopped:
        return f":warning: ronspot-sniper stopped: {stopped}"
    held = [f"{pretty_date(d.date)} — {_bay(d.bay)}" for d in mine]
    lines = [":car: ronspot-sniper report"]
    lines.append("Already yours: " + (", ".join(held) if held else "none"))
    if not pending:
        lines.append("Still missing: nothing, the whole window is covered")
        return "\n".join(lines)
    missing = []
    for date in pending:
        note = ""
        if date == today and not include_today and give_up_at is not None:
            note = f" (given up, past {give_up_at:%H:%M})"
        failures = state.rejected.get(date.isoformat(), 0)
        if failures:
            note += f" ({failures} rejections)"
        missing.append(f"{pretty_date(date)}{note}")
    lines.append("Still missing: " + ", ".join(missing))
    return "\n".join(lines)
