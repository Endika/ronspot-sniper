import datetime as dt

from ronspot_sniper import policy
from ronspot_sniper.client import Day

MAR_JUE = {1, 3}


def day(iso: str, *, mine: bool = False, blocked: bool = False, free: bool = False) -> Day:
    return Day(
        date=dt.date.fromisoformat(iso),
        free_bays=1 if free else 0,
        spot_id=25219 if mine else 0,
        bay="22 Nivel 4" if mine else "",
        blocked=blocked,
        calendar_says_free=free,
    )


def test_wanted_dates_includes_today_because_a_spot_can_free_this_morning():
    martes = dt.date(2026, 9, 22)

    fechas = policy.wanted_dates(martes, 1, MAR_JUE)

    assert fechas == [martes, dt.date(2026, 9, 24)]


def test_wanted_dates_spans_the_whole_horizon():
    fechas = policy.wanted_dates(dt.date(2026, 9, 22), 3, MAR_JUE)

    assert len(fechas) == 6
    assert fechas[-1] == dt.date(2026, 10, 8)
    assert {f.weekday() for f in fechas} == MAR_JUE


def test_candidates_ignores_what_the_calendar_claims_about_availability():
    """El día lleno según el calendario es justo el que resultó reservable."""
    dias = [day("2026-09-29", free=False), day("2026-10-06", free=True)]

    hits = policy.candidates(dias, MAR_JUE, dt.date(2026, 9, 22))

    assert [d.date.isoformat() for d in hits] == ["2026-09-29", "2026-10-06"]


def test_candidates_skips_mine_blocked_past_and_other_weekdays():
    dias = [
        day("2026-09-21"),                 # lunes
        day("2026-09-15"),                 # martes pasado
        day("2026-09-29", mine=True),
        day("2026-10-01", blocked=True),
        day("2026-10-06"),
    ]

    hits = policy.candidates(dias, MAR_JUE, dt.date(2026, 9, 22))

    assert [d.date.isoformat() for d in hits] == ["2026-10-06"]


def test_candidates_come_out_nearest_first():
    dias = [day("2026-10-08"), day("2026-09-24"), day("2026-10-01")]

    hits = policy.candidates(dias, MAR_JUE, dt.date(2026, 9, 22))

    assert [d.date.day for d in hits] == [24, 1, 8]


def test_candidates_honour_the_snipe_window():
    dias = [day("2026-09-24"), day("2026-10-08")]

    hits = policy.candidates(dias, MAR_JUE, dt.date(2026, 9, 22), until=dt.date(2026, 10, 1))

    assert [d.date.isoformat() for d in hits] == ["2026-09-24"]


def test_weeks_to_poll_drops_the_weeks_already_covered():
    hoy = dt.date(2026, 9, 22)
    cubiertos = {dt.date(2026, 9, 22), dt.date(2026, 9, 24)}

    semanas = policy.weeks_to_poll(hoy, 3, MAR_JUE, cubiertos)

    assert semanas == [dt.date(2026, 9, 28), dt.date(2026, 10, 5)]


def test_weeks_to_poll_is_empty_when_everything_is_mine():
    hoy = dt.date(2026, 9, 22)
    todos = set(policy.wanted_dates(hoy, 3, MAR_JUE))

    assert policy.weeks_to_poll(hoy, 3, MAR_JUE, todos) == []
