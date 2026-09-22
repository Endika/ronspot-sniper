import datetime as dt

from ronspot_sniper.__main__ import ZONA_RONSPOT, print_report
from ronspot_sniper.client import Booking
from ronspot_sniper.sniper import Report


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
