import datetime as dt

from ronspot_sniper.domain.state import MAX_BACKOFF, State


def test_backoff_grows_and_then_stops_growing():
    state = State()

    first = state.penalise(now=0.0)
    second = state.penalise(now=0.0)
    for _ in range(20):
        last = state.penalise(now=0.0)

    assert (first, second) == (300.0, 600.0)
    assert last == MAX_BACKOFF


def test_three_rate_limits_leave_the_next_tick_blocked():
    state = State()
    for _ in range(3):
        state.penalise(now=1000.0)

    assert state.blocked(now=1001.0)
    assert not state.blocked(now=1000.0 + 1200.0 + 1)


def test_a_good_answer_clears_the_punishment():
    state = State()
    state.penalise(now=0.0)

    state.relax()

    assert not state.blocked(now=1.0) and state.backoff_level == 0


def test_past_days_are_forgotten_so_the_file_never_grows():
    state = State(
        covered={"2026-09-15": "old", "2026-09-24": "21 Level 4"},
        rejected={"2026-09-15": 3, "2026-09-24": 1},
        confirmed_at={"2026-09-15": 1.0, "2026-09-24": 2.0},
    )

    state.forget_past(dt.date(2026, 9, 22))

    assert list(state.covered) == ["2026-09-24"]
    assert list(state.rejected) == ["2026-09-24"]
    assert list(state.confirmed_at) == ["2026-09-24"]


def test_covered_dates_come_back_as_dates():
    assert State(covered={"2026-09-24": "21 Level 4"}).covered_dates() == {dt.date(2026, 9, 24)}
