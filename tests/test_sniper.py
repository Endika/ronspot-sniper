import datetime as dt
from pathlib import Path
from typing import Any

from ronspot_sniper.client import RonspotClient
from ronspot_sniper.config import Config
from ronspot_sniper.sniper import Report, run_tick
from ronspot_sniper.state import State
from tests.fake import FakeRonspot, FakeSlack

GUID = "00000000-0000-0000-0000-000000000000"
ZONE = 1234
LUNES_ABIERTO = dt.date(2026, 10, 5)


def config(**kwargs: Any) -> Config:
    base = {
        "guid": GUID,
        "zone_id": ZONE,
        "base_url": "https://my.ronspot.ie",
        "vehicle_type_id": 2,
        "vehicle_fuel_id": 2,
        "weekdays": (1, 3),
        "horizon_days": 14,
        "giveup_time": None,
        "local_tz": "Europe/Madrid",
        "resync_seconds": 1800,
        "confirm_tries": 3,
        "confirm_gap": 0.0,
        "notify_kind": "console",
        "notify_options": {},
        "session_path": Path("/dev/null"),
        "state_path": Path("/dev/null"),
    }
    return Config(**{**base, **kwargs})


def tick(
    fake: FakeRonspot,
    state: State | None = None,
    slack: FakeSlack | None = None,
    *,
    today: dt.date = LUNES_ABIERTO,
    now: float = 0.0,
    **kwargs: bool,
) -> tuple[Report, State, FakeSlack]:
    slack = slack or FakeSlack()
    state = state if state is not None else State(last_sweep=now)
    client = RonspotClient({"ci_session": "x"}, GUID, ZONE, transport=fake)
    report = run_tick(config(), state, client, slack, today=today, now=now, **kwargs)
    return report, state, slack


def test_a_free_tuesday_is_claimed_confirmed_and_announced():
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})

    report, state, slack = tick(fake)

    assert [b.date.isoformat() for b in report.booked] == ["2026-10-06"]
    assert report.booked[0].bay == "11 Nivel 3"
    assert state.covered == {"2026-10-06": "11 Nivel 3"}
    assert len(slack.messages) == 1
    assert "martes 06/10" in slack.messages[0] and "11 Nivel 3" in slack.messages[0]


def test_two_days_at_once_are_announced_in_a_single_message():
    fake = FakeRonspot(
        weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06", "2026-10-08"}
    )

    report, _, slack = tick(fake)

    assert len(report.booked) == 2
    assert len(slack.messages) == 1
    assert slack.messages[0].startswith(":car: 2 plazas cogidas")


def test_the_lying_calendar_never_triggers_a_claim():
    """week_open anuncia hueco los 6 días; Ronspot no ofrece coche en ninguno.
    Es el caso que mandó dos notificaciones al móvil, y no debe repetirse."""
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable=set())

    report, _, slack = tick(fake)

    assert report.booked == [] and report.failed == []
    assert [d.isoformat() for d in report.phantom] == ["2026-10-06", "2026-10-08"]
    assert "claimSpot" not in " ".join(fake.paths())
    assert slack.messages == []


def test_days_already_booked_are_left_alone():
    fake = FakeRonspot(
        weeks={"2026-09-28": "week_full.json"}, bookable={"2026-09-29", "2026-10-01"}
    )

    report, state, slack = tick(fake, today=dt.date(2026, 9, 28))

    assert report.booked == []
    assert "claimSpot" not in " ".join(fake.paths())
    assert state.covered == {"2026-09-29": "22 Nivel 4", "2026-10-01": "21 Nivel 4"}
    assert slack.messages == []


def test_a_queued_claim_that_never_confirms_counts_as_rejected():
    fake = FakeRonspot(
        weeks={"2026-10-05": "week_open.json"},
        bookable={"2026-10-06"},
        pending=["pending_wait.json"],
    )
    state = State(last_sweep=0.0)
    client = RonspotClient({"ci_session": "x"}, GUID, ZONE, transport=fake)

    report = run_tick(config(), state, client, FakeSlack(), today=LUNES_ABIERTO, now=0.0)

    assert report.booked == []
    assert state.rejected["2026-10-06"] == 1


def test_a_rejected_day_is_tried_again_on_the_next_tick():
    """Un rechazo suele ser que otro te ha ganado la carrera, no que el día sea imposible."""
    state = State(last_sweep=0.0, rejected={"2026-10-06": 7})
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})

    report, state, _ = tick(fake, state)

    assert [b.date.isoformat() for b in report.booked] == ["2026-10-06"]
    assert "2026-10-06" not in state.rejected


def test_an_expired_cookie_is_announced_once_and_only_once():
    slack = FakeSlack()
    state = State(last_sweep=0.0)
    for _ in range(2):
        fake = FakeRonspot(weeks={"2026-10-05": "login.html"})
        report, state, _ = tick(fake, state, slack)

    assert report.stopped == "sesión caducada"
    assert len(slack.messages) == 1
    assert "caducado" in slack.messages[0]


def test_a_rate_limit_parks_the_next_tick_without_a_single_request():
    fake = FakeRonspot(status=429)

    report, state, _ = tick(fake)
    assert "rate limit 429" in report.stopped
    assert state.blocked(now=1.0)

    otro = FakeRonspot(status=200, weeks={"2026-10-05": "week_open.json"})
    report2, _, _ = tick(otro, state, now=1.0)

    assert report2.stopped == "backoff"
    assert otro.calls == []


def test_dry_run_looks_but_does_not_touch():
    fake = FakeRonspot(
        weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06", "2026-10-08"}
    )

    report, state, slack = tick(fake, dry_run=True)

    assert len(report.booked) == 2
    assert "claimSpot" not in " ".join(fake.paths())
    assert slack.messages == [] and state.covered == {}


def test_the_nightly_router_reboot_is_a_quiet_non_event():
    """Dos minutos sin red cada madrugada: ni Slack, ni backoff, ni estado tocado."""
    fake = FakeRonspot(offline=True)

    report, state, slack = tick(fake)

    assert report.stopped == "sin red"
    assert slack.messages == []
    assert state.backoff_level == 0 and not state.blocked(now=1.0)


def test_after_the_router_is_back_the_next_tick_works_normally():
    state = State(last_sweep=0.0)
    tick(FakeRonspot(offline=True), state)

    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})
    report, state, slack = tick(fake, state)

    assert [b.date.isoformat() for b in report.booked] == ["2026-10-06"]
    assert len(slack.messages) == 1


def test_a_server_error_is_a_quiet_skip_not_a_crash():
    report, state, slack = tick(FakeRonspot(status=503))

    assert report.stopped == "sin red"
    assert slack.messages == [] and state.backoff_level == 0


def test_backoff_escalates_when_the_limit_comes_from_the_vehicle_check():
    """El `relax()` estaba antes del bucle de reservas: el nivel volvía a 0 en cada tic
    y se martilleaba a Ronspot cada 5 minutos para siempre."""
    state = State(last_sweep=0.0)
    esperas = []
    for n in range(3):
        fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, vehicles_status=429)
        antes = state.blocked_until
        tick(fake, state, now=float(n * 10_000))
        esperas.append(state.blocked_until - max(antes, float(n * 10_000)))

    assert esperas == [300.0, 600.0, 1200.0]


def test_a_sweep_does_not_forget_a_booking_the_calendar_has_not_caught_up_with():
    """La cola de Ronspot es asíncrona: si el barrido se fía solo del calendario, olvida
    la reserva recién hecha y la vuelve a pedir, que acaba en rechazo y notificación."""
    state = State(last_sweep=0.0)
    primero = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})
    tick(primero, state, now=0.0)
    assert "2026-10-06" in state.covered

    # El calendario sigue sin reflejarla (week_open no la trae) y ahora toca barrido.
    segundo = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})
    report, state, _ = tick(segundo, state, now=60.0, full_sweep=True)

    assert report.booked == []
    assert "claimSpot" not in " ".join(segundo.paths())
    assert "2026-10-06" in state.covered


def test_the_expiry_alert_is_retried_when_slack_is_down():
    slack = FakeSlack(working=False)
    state = State(last_sweep=0.0)
    _, state, _ = tick(FakeRonspot(weeks={"2026-10-05": "login.html"}), state, slack)

    assert not state.session_alert_sent

    slack.working = True
    _, state, _ = tick(FakeRonspot(weeks={"2026-10-05": "login.html"}), state, slack)

    assert state.session_alert_sent
    assert len(slack.messages) == 2


def test_with_every_target_booked_a_tick_costs_zero_requests():
    """Si no falta ningún martes ni jueves, el tic no habla con Ronspot en absoluto."""
    todos = {
        d.isoformat(): "21 Nivel 4"
        for d in [
            dt.date(2026, 10, 6),
            dt.date(2026, 10, 8),
            dt.date(2026, 10, 13),
            dt.date(2026, 10, 15),
        ]
    }
    state = State(last_sweep=0.0, covered=todos)
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"}, bookable={"2026-10-06"})

    report, _, slack = tick(fake, state, now=60.0)

    assert fake.calls == []
    assert report.polled_weeks == 0 and report.booked == [] and slack.messages == []


def test_the_half_hourly_sweep_still_runs_and_keeps_the_session_warm():
    """Ese barrido es lo que detecta una cancelación ajena y, de paso, no deja morir la
    cookie por inactividad."""
    todos = {
        d.isoformat(): "21 Nivel 4"
        for d in [
            dt.date(2026, 10, 6),
            dt.date(2026, 10, 8),
            dt.date(2026, 10, 13),
            dt.date(2026, 10, 15),
        ]
    }
    state = State(last_sweep=0.0, covered=todos)
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"})

    report, _, _ = tick(fake, state, now=1801.0)

    assert report.polled_weeks == 3
    assert "claimSpot" not in " ".join(fake.paths())
