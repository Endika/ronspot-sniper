import datetime as dt

from ronspot_sniper import policy
from ronspot_sniper.client import Day

MAR_JUE = {1, 3}
HOY = dt.date(2026, 9, 22)  # martes


def day(iso: str, *, mine: bool = False, blocked: bool = False, free: bool = False) -> Day:
    return Day(
        date=dt.date.fromisoformat(iso),
        free_bays=1 if free else 0,
        spot_id=25219 if mine else 0,
        bay="22 Nivel 4" if mine else "",
        blocked=blocked,
        calendar_says_free=free,
    )


def test_the_window_is_the_measured_fourteen_days():
    assert policy.HORIZON_DAYS == 14
    assert policy.window_end(HOY) == dt.date(2026, 10, 6)


def test_wanted_dates_includes_today_because_a_spot_can_free_this_morning():
    fechas = policy.wanted_dates(HOY, MAR_JUE)

    assert fechas[0] == HOY
    assert fechas == [HOY, dt.date(2026, 9, 24), dt.date(2026, 9, 29), dt.date(2026, 10, 1)]


def test_wanted_dates_stops_at_the_edge_of_the_window():
    """El 6-oct está a +14 y Ronspot no deja reservarlo todavía; mirarlo gasta peticiones."""
    assert dt.date(2026, 10, 6) not in policy.wanted_dates(HOY, MAR_JUE)


def test_week_starts_cover_the_window_and_no_more():
    assert policy.week_starts(HOY) == [
        dt.date(2026, 9, 21),
        dt.date(2026, 9, 28),
        dt.date(2026, 10, 5),
    ]


def test_candidates_ignore_what_the_calendar_claims_about_availability():
    """El día que el calendario da por lleno es justo el que resultó reservable."""
    dias = [day("2026-09-29", free=False), day("2026-10-01", free=True)]

    hits = policy.candidates(dias, MAR_JUE, HOY)

    assert [d.date.isoformat() for d in hits] == ["2026-09-29", "2026-10-01"]


def test_candidates_skip_mine_blocked_past_out_of_window_and_other_weekdays():
    dias = [
        day("2026-09-21"),  # lunes
        day("2026-09-15"),  # martes pasado
        day("2026-09-24", mine=True),
        day("2026-09-29", blocked=True),
        day("2026-10-06"),  # fuera de plazo
        day("2026-10-01"),
    ]

    hits = policy.candidates(dias, MAR_JUE, HOY)

    assert [d.date.isoformat() for d in hits] == ["2026-10-01"]


def test_candidates_come_out_nearest_first():
    dias = [day("2026-10-01"), day("2026-09-22"), day("2026-09-29")]

    hits = policy.candidates(dias, MAR_JUE, HOY)

    assert [d.date.day for d in hits] == [22, 29, 1]


def test_weeks_to_poll_drops_the_weeks_already_covered():
    cubiertos = {HOY, dt.date(2026, 9, 24)}

    assert policy.weeks_to_poll(HOY, MAR_JUE, cubiertos) == [dt.date(2026, 9, 28)]


def test_weeks_to_poll_is_empty_when_everything_in_the_window_is_mine():
    todos = set(policy.wanted_dates(HOY, MAR_JUE))

    assert policy.weeks_to_poll(HOY, MAR_JUE, todos) == []


def test_today_is_dropped_once_the_cutoff_has_passed():
    """Pasadas las 09:30 ya estás en la oficina con el coche en la calle: hoy no sirve."""
    dias = [day("2026-09-22"), day("2026-09-24")]

    assert [d.date.day for d in policy.candidates(dias, MAR_JUE, HOY)] == [22, 24]
    hits = policy.candidates(dias, MAR_JUE, HOY, include_today=False)
    assert [d.date.day for d in hits] == [24]


def test_an_abandoned_today_does_not_cost_a_request_either():
    """Si hoy es el único día pendiente y ya pasó la hora de corte, no se pide nada."""
    cubiertos = {dt.date(2026, 9, 24), dt.date(2026, 9, 29), dt.date(2026, 10, 1)}

    assert policy.weeks_to_poll(HOY, MAR_JUE, cubiertos) == [dt.date(2026, 9, 21)]
    assert policy.weeks_to_poll(HOY, MAR_JUE, cubiertos, include_today=False) == []
