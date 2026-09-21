"""Qué días quiero y qué semanas hace falta pedir para saberlo. Sin red."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Iterable, Sequence

from .client import Day

WEEK = dt.timedelta(days=7)

HORIZON_DAYS = 14
"""Medido el 2026-09-22: el último día reservable era hoy+13, y a partir de hoy+14 Ronspot
marca *todos* los días como `Spotavailable: 1` sin dejar reservar ninguno. Mirar más lejos
solo gasta peticiones."""


def monday_of(date: dt.date) -> dt.date:
    return date - dt.timedelta(days=date.weekday())


def window_end(today: dt.date, horizon_days: int = HORIZON_DAYS) -> dt.date:
    """Primer día ya fuera de plazo."""
    return today + dt.timedelta(days=horizon_days)


def week_starts(today: dt.date, horizon_days: int = HORIZON_DAYS) -> list[dt.date]:
    """Los lunes que hacen falta para cubrir la ventana: dos o tres peticiones."""
    first, last = monday_of(today), monday_of(window_end(today, horizon_days))
    return [first + WEEK * n for n in range((last - first).days // 7 + 1)]


def wanted_dates(
    today: dt.date,
    weekdays: Collection[int],
    horizon_days: int = HORIZON_DAYS,
) -> list[dt.date]:
    """Los martes y jueves en plazo, hoy incluido: un hueco se puede liberar esta mañana."""
    end = window_end(today, horizon_days)
    day, out = today, []
    while day < end:
        if day.weekday() in weekdays:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def weeks_to_poll(
    today: dt.date,
    weekdays: Collection[int],
    covered: Collection[dt.date],
    horizon_days: int = HORIZON_DAYS,
) -> list[dt.date]:
    """Solo las semanas con algún día objetivo que aún no tengo."""
    pending = [d for d in wanted_dates(today, weekdays, horizon_days) if d not in covered]
    return sorted({monday_of(d) for d in pending})


def candidates(
    days: Iterable[Day],
    weekdays: Collection[int],
    today: dt.date,
    horizon_days: int = HORIZON_DAYS,
) -> list[Day]:
    """Días objetivo en plazo que aún no son míos, el más cercano primero.

    No se filtra por `Spotavailable`: fuera de plazo vale 1 en todos los días y dentro no
    es de fiar. Quien dice si hay plaza es `RonspotClient.bookable()`.
    """
    end = window_end(today, horizon_days)
    hits = [
        day for day in days
        if day.date.weekday() in weekdays and today <= day.date < end and day.worth_trying
    ]
    return sorted(hits, key=lambda d: d.date)


def already_mine(
    days: Iterable[Day],
    weekdays: Collection[int],
    today: dt.date,
    horizon_days: int = HORIZON_DAYS,
) -> list[Day]:
    """Lo que ya tengo dentro de la ventana. Fuera de ella no hay nada que cubrir."""
    end = window_end(today, horizon_days)
    return sorted(
        (day for day in days
         if day.mine and day.date.weekday() in weekdays and today <= day.date < end),
        key=lambda d: d.date,
    )


def flatten(weeks: Sequence[object]) -> list[Day]:
    out: list[Day] = []
    for week in weeks:
        out.extend(getattr(week, "days", ()))
    return out
