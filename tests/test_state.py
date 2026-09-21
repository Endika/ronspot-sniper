import datetime as dt

from ronspot_sniper.state import MAX_BACKOFF, State


def test_backoff_grows_and_then_stops_growing():
    state = State()

    primero = state.penalise(now=0.0)
    segundo = state.penalise(now=0.0)
    for _ in range(20):
        ultimo = state.penalise(now=0.0)

    assert (primero, segundo) == (300.0, 600.0)
    assert ultimo == MAX_BACKOFF


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


def test_state_survives_a_round_trip(tmp_path):
    path = tmp_path / "state.json"
    original = State(covered={"2026-09-24": "21 Nivel 4"}, rejected={"2026-09-22": 2},
                     backoff_level=2, last_sweep=99.0)

    original.save(path)
    leido = State.load(path)

    assert leido == original
    assert path.stat().st_mode & 0o777 == 0o600


def test_a_corrupt_state_file_does_not_stop_the_tick(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ esto no es json")

    assert State.load(path) == State()


def test_missing_state_file_starts_from_scratch(tmp_path):
    assert State.load(tmp_path / "nada.json") == State()


def test_unknown_keys_from_an_older_version_are_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"covered": {}, "campo_que_ya_no_existe": 1}')

    assert State.load(path) == State()


def test_past_days_are_forgotten_so_the_file_never_grows():
    state = State(covered={"2026-09-15": "vieja", "2026-09-24": "21 Nivel 4"},
                  rejected={"2026-09-15": 3, "2026-09-24": 1})

    state.forget_past(dt.date(2026, 9, 22))

    assert state.covered == {"2026-09-24": "21 Nivel 4"}
    assert state.rejected == {"2026-09-24": 1}


def test_covered_dates_come_back_as_dates():
    state = State(covered={"2026-09-24": "21 Nivel 4"})

    assert state.covered_dates() == {dt.date(2026, 9, 24)}
