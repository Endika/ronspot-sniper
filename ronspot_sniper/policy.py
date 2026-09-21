"""Qué días quiero y qué semanas hace falta pedir para saberlo. Sin red."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Iterable, Sequence

from .client import Day

WEEK = dt.timedelta(days=7)


def monday_of(date: dt.date) -> dt.date:
    return date - dt.timedelta(days=date.weekday())


def week_starts(today: dt.date, max_weeks: int) -> list[dt.date]:
    first = monday_of(today)
    return [first + WEEK * n for n in range(max_weeks)]


def wanted_dates(today: dt.date, max_weeks: int, weekdays: Collection[int]) -> list[dt.date]:
    """Los martes y jueves del horizonte, hoy incluido: un hueco se puede liberar esta mañana."""
    start = monday_of(today)
    end = start + WEEK * max_weeks
    day = max(start, today)
    out = []
    while day < end:
        if day.weekday() in weekdays:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def weeks_to_poll(
    today: dt.date,
    max_weeks: int,
    weekdays: Collection[int],
    covered: Collection[dt.date],
) -> list[dt.date]:
    """Solo las semanas con algún día objetivo que aún no tengo. En régimen son una o dos."""
    pending = [d for d in wanted_dates(today, max_weeks, weekdays) if d not in covered]
    return sorted({monday_of(d) for d in pending})


def candidates(
    days: Iterable[Day],
    weekdays: Collection[int],
    today: dt.date,
    until: dt.date | None = None,
) -> list[Day]:
    """Días objetivo que aún no son míos, el más cercano primero: es el que antes vuela.

    No se filtra por `Spotavailable`: está medido que miente. Quien dice si hay plaza es
    `RonspotClient.bookable()`, y eso cuesta una petición por día, de ahí el `until`.
    """
    hits = [
        day for day in days
        if day.date.weekday() in weekdays and day.date >= today and day.worth_trying
        and (until is None or day.date < until)
    ]
    return sorted(hits, key=lambda d: d.date)


def already_mine(days: Iterable[Day], weekdays: Collection[int]) -> list[Day]:
    return sorted(
        (day for day in days if day.mine and day.date.weekday() in weekdays),
        key=lambda d: d.date,
    )


def flatten(weeks: Sequence[object]) -> list[Day]:
    out: list[Day] = []
    for week in weeks:
        out.extend(getattr(week, "days", ()))
    return out
