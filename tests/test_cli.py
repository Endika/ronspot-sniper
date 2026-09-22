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


def test_the_cutoff_clock_is_yours_and_configurable():
    """Las fechas van en la zona de Ronspot, pero "ya estoy en la oficina" es tu reloj,
    y quien use esto desde otro país necesita poder cambiarlo."""
    from ronspot_sniper.config import Config

    campos = Config.__dataclass_fields__
    assert "local_tz" in campos
    assert str(ZONA_RONSPOT) == "Europe/Dublin"


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


def test_without_a_slack_token_the_alerts_fall_back_to_the_console(capsys):
    """Quien no use Slack no puede quedarse sin enterarse: sale por el log del cron."""
    from ronspot_sniper.__main__ import avisador
    from ronspot_sniper.notify import Console, Discord, Notifier, Slack
    from tests.test_sniper import config

    def hecho(kind: str, **options: str) -> Notifier:
        return avisador(config(notify_kind=kind, notify_options=options))

    assert isinstance(hecho("console"), Console)
    assert isinstance(hecho("slack", token="t", channel="c"), Slack)
    assert isinstance(hecho("discord", webhook="https://discord.com/api/webhooks/x"), Discord)

    hecho("console").send("hola")
    assert "hola" in capsys.readouterr().out


def test_a_missing_config_says_what_to_do_instead_of_a_traceback(tmp_path, capsys):
    """Es la primera piedra con la que tropieza cualquiera que clone el repo."""
    from ronspot_sniper.__main__ import main

    codigo = main(["--config", str(tmp_path / "no-existe.toml"), "--status"])

    error = capsys.readouterr().err
    assert codigo == 2
    assert "no encuentro el config" in error
    assert "capture.mjs" in error
    assert "Traceback" not in error


def test_a_missing_cookie_says_how_to_get_one(tmp_path, capsys):
    from ronspot_sniper.__main__ import main

    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[ronspot]\nguid = "x"\nzone_id = 1\n'
        f'[paths]\nsession = "{tmp_path / "falta.json"}"\nstate = "{tmp_path / "s.json"}"\n'
    )

    codigo = main(["--config", str(cfg), "--status"])

    error = capsys.readouterr().err
    assert codigo == 2
    assert "cookie de sesión" in error and "capture.mjs" in error


def test_a_broken_config_points_at_the_example(tmp_path, capsys):
    from ronspot_sniper.__main__ import main

    cfg = tmp_path / "config.toml"
    cfg.write_text("esto no es toml [[[")

    codigo = main(["--config", str(cfg), "--status"])

    assert codigo == 2
    assert "config.example.toml" in capsys.readouterr().err


def test_an_unknown_notifier_is_a_message_not_a_crash(tmp_path, capsys):
    from ronspot_sniper.__main__ import main

    cfg = tmp_path / "config.toml"
    session = tmp_path / "session.json"
    session.write_text(
        '{"cookies": [{"name": "ci_session", "value": "x", "domain": "ronspot.ie"}]}'
    )
    cfg.write_text(
        '[ronspot]\nguid = "x"\nzone_id = 1\n'
        '[notify]\nkind = "telegrama"\n'
        f'[paths]\nsession = "{session}"\nstate = "{tmp_path / "s.json"}"\n'
    )

    codigo = main(["--config", str(cfg), "--dry-run"])

    assert codigo == 2
    assert "telegrama" in capsys.readouterr().err
