import datetime as dt
from zoneinfo import ZoneInfo

from ronspot_sniper.domain import policy
from tests.fakes import day

TUE_THU = frozenset({1, 3})
TODAY = dt.date(2026, 9, 22)  # a Tuesday


def test_the_window_is_the_measured_fourteen_days():
    assert policy.HORIZON_DAYS == 14
    assert policy.window_end(TODAY) == dt.date(2026, 10, 6)


def test_wanted_dates_includes_today_because_a_spot_can_free_this_morning():
    assert policy.wanted_dates(TODAY, TUE_THU)[0] == TODAY


def test_wanted_dates_stops_at_the_edge_of_the_window():
    """6 Oct is today+14: Ronspot will not book it yet, and asking costs a request."""
    assert dt.date(2026, 10, 6) not in policy.wanted_dates(TODAY, TUE_THU)


def test_week_starts_cover_the_window_and_no_more():
    assert policy.week_starts(TODAY) == [
        dt.date(2026, 9, 21),
        dt.date(2026, 9, 28),
        dt.date(2026, 10, 5),
    ]


def test_candidates_ignore_what_the_calendar_claims_about_availability():
    """The day the calendar calls full is exactly the one that turned out bookable."""
    days = [day("2026-09-29", free=False), day("2026-10-01", free=True)]

    hits = policy.candidates(days, TUE_THU, TODAY)

    assert [d.date.isoformat() for d in hits] == ["2026-09-29", "2026-10-01"]


def test_candidates_skip_mine_blocked_past_out_of_window_and_other_weekdays():
    days = [
        day("2026-09-21"),  # Monday
        day("2026-09-15"),  # a Tuesday in the past
        day("2026-09-24", mine=True),
        day("2026-09-29", blocked=True),
        day("2026-10-06"),  # out of window
        day("2026-10-01"),
    ]

    hits = policy.candidates(days, TUE_THU, TODAY)

    assert [d.date.isoformat() for d in hits] == ["2026-10-01"]


def test_candidates_come_out_nearest_first():
    days = [day("2026-10-01"), day("2026-09-22"), day("2026-09-29")]

    assert [d.date.day for d in policy.candidates(days, TUE_THU, TODAY)] == [22, 29, 1]


def test_today_is_dropped_once_the_cutoff_has_passed():
    """Past 09:30 you are at the office with the car parked in the street."""
    days = [day("2026-09-22"), day("2026-09-24")]

    assert [d.date.day for d in policy.candidates(days, TUE_THU, TODAY)] == [22, 24]
    late = policy.candidates(days, TUE_THU, TODAY, include_today=False)
    assert [d.date.day for d in late] == [24]


def test_weeks_to_poll_drops_the_weeks_already_covered():
    covered = {TODAY, dt.date(2026, 9, 24)}

    assert policy.weeks_to_poll(TODAY, TUE_THU, covered) == [dt.date(2026, 9, 28)]


def test_weeks_to_poll_is_empty_when_everything_in_the_window_is_mine():
    everything = set(policy.wanted_dates(TODAY, TUE_THU))

    assert policy.weeks_to_poll(TODAY, TUE_THU, everything) == []


def test_an_abandoned_today_does_not_cost_a_request_either():
    covered = {dt.date(2026, 9, 24), dt.date(2026, 9, 29), dt.date(2026, 10, 1)}

    assert policy.weeks_to_poll(TODAY, TUE_THU, covered) == [dt.date(2026, 9, 21)]
    assert policy.weeks_to_poll(TODAY, TUE_THU, covered, include_today=False) == []


def test_already_mine_only_looks_inside_the_window():
    days = [day("2026-09-15", mine=True), day("2026-09-24", mine=True)]

    held = policy.already_mine(days, TUE_THU, TODAY)

    assert [d.date.isoformat() for d in held] == ["2026-09-24"]


MADRID = ZoneInfo("Europe/Madrid")


def test_today_is_chased_until_the_cutoff_in_local_time():
    morning = dt.datetime(2026, 9, 22, 9, 29, tzinfo=MADRID)
    late = dt.datetime(2026, 9, 22, 9, 30, tzinfo=MADRID)

    assert policy.still_chasing_today(TODAY, morning, dt.time(9, 30))
    assert not policy.still_chasing_today(TODAY, late, dt.time(9, 30))


def test_dublins_today_is_already_yesterday_in_madrid_between_midnight_and_one():
    """At 00:30 in Madrid Ronspot still says 22/09: that day is over, not before the cutoff."""
    after_midnight = dt.datetime(2026, 9, 23, 0, 30, tzinfo=MADRID)

    assert not policy.still_chasing_today(TODAY, after_midnight, dt.time(9, 30))
    assert not policy.still_chasing_today(TODAY, after_midnight, None)


def test_without_a_cutoff_today_is_chased_all_day():
    night = dt.datetime(2026, 9, 22, 23, 59, tzinfo=MADRID)

    assert policy.still_chasing_today(TODAY, night, None)
