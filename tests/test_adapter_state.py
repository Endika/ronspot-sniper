import datetime as dt

import pytest

from ronspot_sniper.adapters.state import load_state, save_state
from ronspot_sniper.domain.state import State


def test_state_survives_a_round_trip(tmp_path):
    path = tmp_path / "state.json"
    original = State(
        covered={"2026-09-24": "21 Level 4"},
        rejected={"2026-09-22": 2},
        confirmed_at={"2026-09-24": 1.5},
        backoff_level=2,
        last_sweep=99.0,
    )

    save_state(original, path)

    assert load_state(path) == original
    assert path.stat().st_mode & 0o777 == 0o600


def test_a_missing_file_starts_from_scratch(tmp_path):
    assert load_state(tmp_path / "nothing.json") == State()


def test_unknown_keys_from_an_older_version_are_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"covered": {}, "field_that_no_longer_exists": 1}')

    assert load_state(path) == State()


@pytest.mark.parametrize(
    "broken",
    [
        "not json at all {",
        '{"covered": null}',
        '{"covered": ["2026-10-06"]}',
        '{"covered": {"not-a-date": "x"}}',
        '{"blocked_until": "tomorrow"}',
        '{"rejected": {"2026-13-40": 1}}',
        '{"confirmed_at": {"yesterday": 1.0}}',
        '["not even an object"]',
    ],
)
def test_a_malformed_state_file_starts_from_scratch_instead_of_crashing(tmp_path, broken):
    """A corrupt state.json used to mean one traceback a minute until deleted by hand."""
    path = tmp_path / "state.json"
    path.write_text(broken)

    loaded = load_state(path)

    assert loaded == State()
    loaded.forget_past(dt.date(2026, 9, 22))
