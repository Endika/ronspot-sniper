import datetime as dt

from ronspot_sniper.__main__ import ZONA_RONSPOT, print_report, resumen
from ronspot_sniper.client import Booking, Day
from ronspot_sniper.sniper import Report
from ronspot_sniper.state import State


def test_backoff_and_outages_stay_out_of_the_log(capsys):
    """Los dos ocurren cada minuto; imprimirlos llenaría un log que debe estar vacío."""
    for parado in ("backoff", "sin red", "sin red al reservar"):
        print_report(Report(stopped=parado), dry_run=False)

    assert capsys.readouterr().out == ""


def test_a_real_stop_is_printed(capsys):
    print_report(Report(stopped="sesión caducada"), dry_run=False)

    assert "sesión caducada" in capsys.readouterr().out


def test_a_booking_is_printed_with_its_bay(capsys):
    print_report(Report(booked=[Booking(dt.date(2026, 10, 6), 25228, "11 Nivel 3")]), False)

    salida = capsys.readouterr().out
    assert "martes 06/10" in salida and "11 Nivel 3" in salida


def test_the_day_is_ronspots_not_the_pis():
    """El Pi va en Madrid y Ronspot en Dublín: entre las 00:00 y la 01:00 la fecha local
    va un día por delante y la ventana de 14 días se desplaza entera."""
    assert str(ZONA_RONSPOT) == "Europe/Dublin"


def test_the_cutoff_is_read_from_the_config():
    import datetime as dt

    from ronspot_sniper.config import _parse_time

    assert _parse_time("09:30") == dt.time(9, 30)
    assert _parse_time(None) is None
    assert _parse_time("") is None


def test_the_cutoff_clock_is_madrid_not_dublin():
    """Las fechas van en la zona de Ronspot, pero "ya estoy en la oficina" es tu reloj."""
    from ronspot_sniper.__main__ import ZONA_LOCAL

    assert str(ZONA_LOCAL) == "Europe/Madrid"


def _report_state() -> tuple[Report, State]:
    mio = Day(
        date=dt.date(2026, 10, 8),
        free_bays=0,
        spot_id=25215,
        bay="21 Nivel 4",
        blocked=False,
        calendar_says_free=False,
    )
    return Report(mine=[mio]), State(rejected={"2026-10-06": 3})


def test_the_morning_report_covers_the_case_that_sends_no_message():
    """Pillar una plaza ya avisa solo; lo que no avisa de nada es NO pillarla."""
    report, state = _report_state()
    texto = resumen(
        report,
        [dt.date(2026, 10, 6)],
        state,
        dt.time(9, 30),
        dt.date(2026, 10, 6),
        include_today=False,
    )

    assert "jueves 08/10 — 21 Nivel 4" in texto
    assert "martes 06/10" in texto
    assert "abandonado, pasadas las 09:30" in texto
    assert "3 rechazos" in texto


def test_the_morning_report_says_so_when_nothing_is_missing():
    report, _ = _report_state()
    texto = resumen(
        report, [], report_state := _report_state()[1], None, dt.date(2026, 10, 6), True
    )

    assert "la ventana está cubierta entera" in texto
    assert report_state is not None


def test_the_morning_report_shouts_when_the_sniper_is_stuck():
    from ronspot_sniper.__main__ import resumen

    texto = resumen(
        Report(stopped="sesión caducada"),
        [],
        State(),
        None,
        dt.date(2026, 10, 6),
        include_today=True,
    )

    assert texto.startswith(":warning:") and "sesión caducada" in texto


def test_every_documented_flag_actually_exists():
    """El `--report` se quedó sin cablear y los tests del resumen no lo vieron."""
    from ronspot_sniper.__main__ import build_parser

    for bandera in ("--dry-run", "--status", "--report", "--verbose", "--config"):
        args = build_parser().parse_args([bandera] if bandera != "--config" else [bandera, "/x"])
        assert args is not None
