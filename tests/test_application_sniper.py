"""The use case against an in-memory parking service. No HTTP anywhere in here."""

import datetime as dt
from typing import Any

from ronspot_sniper.application import TickReport, run_tick
from ronspot_sniper.domain import Day, SniperConfig
from ronspot_sniper.domain.state import State
from ronspot_sniper.ports import RateLimited, SessionExpired, Unreachable
from tests.fakes import FakeGateway, FakeNotifier, day

TODAY = dt.date(2026, 10, 5)  # a Monday
TUE, THU = dt.date(2026, 10, 6), dt.date(2026, 10, 8)


def config(**kwargs: Any) -> SniperConfig:
    base = {
        "weekdays": frozenset({1, 3}),
        "horizon_days": 14,
        "resync_seconds": 1800,
        "confirm_tries": 3,
        "confirm_gap": 0.0,
    }
    return SniperConfig(**{**base, **kwargs})


def tick(
    gateway: FakeGateway,
    state: State | None = None,
    notifier: FakeNotifier | None = None,
    *,
    now: float = 0.0,
    **kwargs: bool,
) -> tuple[TickReport, State, FakeNotifier]:
    state = state if state is not None else State()
    notifier = notifier or FakeNotifier()
    report = run_tick(gateway, state, notifier, config(), today=TODAY, now=now, **kwargs)
    return report, state, notifier


def open_week() -> list[Day]:
    return [day("2026-10-06"), day("2026-10-07"), day("2026-10-08")]


def test_a_free_tuesday_is_claimed_confirmed_and_announced():
    gateway = FakeGateway(open_week(), bookable={"2026-10-06"})

    report, state, notifier = tick(gateway)

    assert [b.date for b in report.booked] == [TUE]
    assert report.booked[0].bay == "11 Level 3"
    assert state.covered == {"2026-10-06": "11 Level 3"}
    assert notifier.messages == [":car: Spot booked for Tuesday 06/10 — 11 Level 3"]


def test_two_days_at_once_are_announced_in_a_single_message():
    gateway = FakeGateway(open_week(), bookable={"2026-10-06", "2026-10-08"})

    report, _, notifier = tick(gateway)

    assert len(report.booked) == 2
    assert len(notifier.messages) == 1
    assert notifier.messages[0].startswith(":car: 2 spots booked")


def test_the_lying_calendar_never_triggers_a_claim():
    """Every day claims to be free and none is bookable. This is the case that sent two
    notifications to a phone at one in the morning; it must not happen again."""
    gateway = FakeGateway([day(d, free=True) for d in ("2026-10-06", "2026-10-08")], bookable=set())

    report, _, notifier = tick(gateway)

    assert report.booked == [] and report.failed == []
    assert report.phantom == [TUE, THU]
    assert not gateway.did("claim")
    assert notifier.messages == []


def test_days_already_booked_are_left_alone():
    gateway = FakeGateway(
        [day("2026-10-06", mine=True), day("2026-10-08", mine=True)],
        bookable={"2026-10-06", "2026-10-08"},
    )

    report, state, notifier = tick(gateway)

    assert report.booked == [] and not gateway.did("claim")
    assert set(state.covered) == {"2026-10-06", "2026-10-08"}
    assert notifier.messages == []


def test_a_rejected_claim_is_counted_and_not_announced():
    gateway = FakeGateway(open_week(), bookable={"2026-10-06"}, claim_accepted=False)

    report, state, notifier = tick(gateway)

    assert report.booked == [] and report.failed[0][0] == TUE
    assert state.rejected["2026-10-06"] == 1
    assert notifier.messages == []


def test_a_queued_claim_that_never_confirms_counts_as_rejected():
    gateway = FakeGateway(open_week(), bookable={"2026-10-06"}, confirms=False)

    report, state, _ = tick(gateway)

    assert report.booked == []
    assert state.rejected["2026-10-06"] == 1


def test_a_rejected_day_is_tried_again_on_the_next_tick():
    """A rejection usually means somebody beat you to it, not that the day is impossible."""
    gateway = FakeGateway(open_week(), bookable={"2026-10-06"})

    report, state, _ = tick(gateway, State(rejected={"2026-10-06": 7}))

    assert [b.date for b in report.booked] == [TUE]
    assert "2026-10-06" not in state.rejected


def test_a_sweep_does_not_forget_a_booking_the_calendar_has_not_caught_up_with():
    """Ronspot's queue is asynchronous: trusting only the calendar during a sweep drops
    the fresh booking and asks for it again, ending in a rejection and a notification."""
    state = State()
    first = FakeGateway(open_week(), bookable={"2026-10-06"})
    tick(first, state, now=0.0)
    assert "2026-10-06" in state.covered

    second = FakeGateway(open_week(), bookable={"2026-10-06"})
    report, state, _ = tick(second, state, now=60.0, full_sweep=True)

    assert report.booked == [] and not second.did("claim")
    assert "2026-10-06" in state.covered


def test_with_every_target_booked_a_tick_costs_nothing():
    covered = dict.fromkeys(("2026-10-06", "2026-10-08", "2026-10-13", "2026-10-15"), "21 Level 4")
    gateway = FakeGateway(open_week(), bookable={"2026-10-06"})

    report, _, notifier = tick(gateway, State(covered=covered), now=60.0)

    assert gateway.calls == []
    assert report.polled_weeks == 0 and notifier.messages == []


def test_the_half_hourly_sweep_still_runs_and_keeps_the_session_warm():
    covered = dict.fromkeys(("2026-10-06", "2026-10-08", "2026-10-13", "2026-10-15"), "21 Level 4")
    gateway = FakeGateway(open_week())

    report, _, _ = tick(gateway, State(covered=covered), now=1801.0)

    assert report.polled_weeks == 3 and not gateway.did("claim")


def test_the_nightly_router_reboot_is_a_quiet_non_event():
    """Two minutes without network every morning: no alert, no backoff, no state change."""
    gateway = FakeGateway(raises=Unreachable("router"))

    report, state, notifier = tick(gateway)

    assert report.stopped == "no network"
    assert notifier.messages == [] and state.backoff_level == 0


def test_after_the_router_is_back_the_next_tick_works_normally():
    state = State()
    tick(FakeGateway(raises=Unreachable("router")), state)

    report, state, notifier = tick(FakeGateway(open_week(), bookable={"2026-10-06"}), state)

    assert [b.date for b in report.booked] == [TUE]
    assert len(notifier.messages) == 1


def test_a_rate_limit_parks_the_next_tick_without_a_single_request():
    state = State()
    report, state, _ = tick(FakeGateway(raises=RateLimited(429)), state)
    assert "rate limit 429" in report.stopped

    quiet = FakeGateway(open_week(), bookable={"2026-10-06"})
    report2, _, _ = tick(quiet, state, now=1.0)

    assert report2.stopped == "backoff" and quiet.calls == []


def test_backoff_escalates_when_the_limit_comes_from_the_vehicle_check():
    """`relax()` used to run before the booking loop, so the level reset every tick and
    Ronspot got hammered every five minutes forever."""
    state = State()
    waits = []
    for n in range(3):
        gateway = FakeGateway(open_week(), raises=RateLimited(429), raises_on="bookable")
        before = state.blocked_until
        tick(gateway, state, now=float(n * 10_000))
        waits.append(state.blocked_until - max(before, float(n * 10_000)))

    assert waits == [300.0, 600.0, 1200.0]


def test_the_expiry_alert_is_sent_once_and_retried_when_the_notifier_is_down():
    notifier = FakeNotifier(working=False)
    state = State()
    _, state, _ = tick(FakeGateway(raises=SessionExpired("login")), state, notifier)
    assert not state.session_alert_sent

    notifier.working = True
    _, state, _ = tick(FakeGateway(raises=SessionExpired("login")), state, notifier)
    assert state.session_alert_sent

    _, state, _ = tick(FakeGateway(raises=SessionExpired("login")), state, notifier)
    assert len(notifier.messages) == 2


def test_dry_run_looks_but_does_not_touch():
    gateway = FakeGateway(open_week(), bookable={"2026-10-06", "2026-10-08"})

    report, state, notifier = tick(gateway, dry_run=True)

    assert len(report.booked) == 2
    assert not gateway.did("claim")
    assert notifier.messages == [] and state.covered == {}


def test_the_cutoff_keeps_the_tick_off_the_current_day():
    gateway = FakeGateway([day("2026-10-05"), day("2026-10-06")], bookable={"2026-10-06"})

    report, _, _ = tick(gateway, include_today=False)

    assert [b.date for b in report.booked] == [TUE]
