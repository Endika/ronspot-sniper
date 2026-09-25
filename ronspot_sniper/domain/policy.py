"""Which days to chase, and which weeks must be read to find out. Pure functions."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Iterable

from .models import Day

WEEK = dt.timedelta(days=7)

HORIZON_DAYS = 14
"""Measured on 2026-09-22: the last bookable day was today+13, and from today+14 onwards
Ronspot marks *every* day as `Spotavailable: 1` while letting you book none of them.
Looking further only spends requests."""


def monday_of(date: dt.date) -> dt.date:
    return date - dt.timedelta(days=date.weekday())


def window_end(today: dt.date, horizon_days: int = HORIZON_DAYS) -> dt.date:
    """First day already out of the booking window."""
    return today + dt.timedelta(days=horizon_days)


def week_starts(today: dt.date, horizon_days: int = HORIZON_DAYS) -> list[dt.date]:
    """The Mondays needed to cover the window: two or three requests."""
    first, last = monday_of(today), monday_of(window_end(today, horizon_days))
    return [first + WEEK * n for n in range((last - first).days // 7 + 1)]


def wanted_dates(
    today: dt.date,
    weekdays: Collection[int],
    horizon_days: int = HORIZON_DAYS,
) -> list[dt.date]:
    """Target weekdays inside the window, today included: a spot can free up this morning."""
    end = window_end(today, horizon_days)
    day, out = today, []
    while day < end:
        if day.weekday() in weekdays:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def still_chasing_today(today: dt.date, local_now: dt.datetime, give_up_at: dt.time | None) -> bool:
    """`today` is Ronspot's date, the cutoff is local: between midnight and 1am in Madrid,
    Dublin's today is a day that has already gone by, not one still before 09:30."""
    local_today = local_now.date()
    if local_today != today:
        return local_today < today
    return give_up_at is None or local_now.time() < give_up_at


def weeks_to_poll(
    today: dt.date,
    weekdays: Collection[int],
    covered: Collection[dt.date],
    horizon_days: int = HORIZON_DAYS,
    include_today: bool = True,
) -> list[dt.date]:
    """Only the weeks holding a target day I do not have yet.

    When today has already been given up on, its week is not requested either: no point
    spending a request a minute on a day that is no longer useful.
    """
    first = today if include_today else today + dt.timedelta(days=1)
    pending = [
        d for d in wanted_dates(today, weekdays, horizon_days) if d not in covered and d >= first
    ]
    return sorted({monday_of(d) for d in pending})


def candidates(
    days: Iterable[Day],
    weekdays: Collection[int],
    today: dt.date,
    horizon_days: int = HORIZON_DAYS,
    include_today: bool = True,
) -> list[Day]:
    """In-window target days that are not mine yet, nearest first.

    Not filtered by `calendar_says_free`: out of window it reads 1 on every day, and in
    window it is not trustworthy either. Whether a spot exists is the gateway's answer.
    """
    end = window_end(today, horizon_days)
    first = today if include_today else today + dt.timedelta(days=1)
    hits = [
        day
        for day in days
        if day.date.weekday() in weekdays and first <= day.date < end and day.worth_trying
    ]
    return sorted(hits, key=lambda d: d.date)


def already_mine(
    days: Iterable[Day],
    weekdays: Collection[int],
    today: dt.date,
    horizon_days: int = HORIZON_DAYS,
) -> list[Day]:
    """What I already hold inside the window. Outside it there is nothing to cover."""
    end = window_end(today, horizon_days)
    return sorted(
        (
            day
            for day in days
            if day.mine and day.date.weekday() in weekdays and today <= day.date < end
        ),
        key=lambda d: d.date,
    )
