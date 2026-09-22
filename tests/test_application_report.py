import datetime as dt

from ronspot_sniper.application import daily_summary, pretty_date, spots_taken
from ronspot_sniper.domain import Booking
from ronspot_sniper.domain.state import State
from tests.fakes import day

TUE = dt.date(2026, 10, 6)


def test_one_spot_reads_as_a_sentence():
    assert spots_taken([Booking(TUE, 1, "11 Level 3")]) == (
        ":car: Spot booked for Tuesday 06/10 — 11 Level 3"
    )


def test_several_spots_go_in_one_message_not_one_each():
    text = spots_taken([Booking(TUE, 1, "11 Level 3"), Booking(dt.date(2026, 10, 8), 2, "")])

    assert text.startswith(":car: 2 spots booked")
    assert "Thursday 08/10 — no number" in text


def test_pretty_date_names_the_weekday():
    assert pretty_date(dt.date(2026, 10, 8)) == "Thursday 08/10"


def test_the_report_covers_the_case_that_sends_no_message():
    """Winning a spot already alerts you; what alerts nobody is NOT winning one."""
    text = daily_summary(
        [day("2026-10-08", mine=True, bay="21 Level 4")],
        [TUE],
        State(rejected={"2026-10-06": 3}),
        today=TUE,
        give_up_at=dt.time(9, 30),
        include_today=False,
    )

    assert "Thursday 08/10 — 21 Level 4" in text
    assert "Tuesday 06/10" in text
    assert "given up, past 09:30" in text
    assert "3 rejections" in text


def test_the_report_says_so_when_nothing_is_missing():
    text = daily_summary([], [], State(), today=TUE, give_up_at=None, include_today=True)

    assert "the whole window is covered" in text
    assert "Already yours: none" in text


def test_the_report_shouts_when_the_sniper_is_stuck():
    text = daily_summary(
        [], [], State(), today=TUE, give_up_at=None, include_today=True, stopped="session expired"
    )

    assert text.startswith(":warning:") and "session expired" in text
