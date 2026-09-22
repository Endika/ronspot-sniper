import datetime as dt

from ronspot_sniper.application import TickReport
from ronspot_sniper.cli.main import RONSPOT_TZ, bail, build_parser, print_report
from ronspot_sniper.domain import Booking


def test_backoff_and_outages_stay_out_of_the_log(capsys):
    """Both happen every minute; printing them would fill a log meant to stay empty."""
    for stopped in ("backoff", "no network"):
        print_report(TickReport(stopped=stopped), dry_run=False)

    assert capsys.readouterr().out == ""


def test_a_real_stop_is_printed(capsys):
    print_report(TickReport(stopped="session expired"), dry_run=False)

    assert "session expired" in capsys.readouterr().out


def test_a_booking_is_printed_with_its_bay(capsys):
    print_report(TickReport(booked=[Booking(dt.date(2026, 10, 6), 1, "11 Level 3")]), False)

    out = capsys.readouterr().out
    assert "Tuesday 06/10" in out and "11 Level 3" in out


def test_the_day_is_ronspots_not_the_machines():
    """Ronspot runs on Dublin time; using the local date shifts the window by a day
    between midnight and 1am in Madrid."""
    assert str(RONSPOT_TZ) == "Europe/Dublin"


def test_the_cutoff_clock_is_configurable():
    from ronspot_sniper.config import Settings

    assert "local_tz" in Settings.__dataclass_fields__


def test_bail_writes_one_sentence_to_stderr_and_returns_two(capsys):
    code = bail("no config at /x", "run this instead")

    err = capsys.readouterr().err
    assert code == 2
    assert "no config at /x" in err and "run this instead" in err
    assert "Traceback" not in err


def test_every_documented_flag_actually_exists():
    """`--report` once shipped uncabled, and the summary tests never noticed."""
    for flag in ("--dry-run", "--status", "--report", "--verbose"):
        assert build_parser().parse_args([flag]) is not None
    assert build_parser().parse_args(["--config", "/x"]).config.name == "x"


def test_a_missing_config_says_what_to_do_instead_of_a_traceback(tmp_path, capsys):
    from ronspot_sniper.cli import main

    code = main(["--config", str(tmp_path / "missing.toml"), "--status"])

    err = capsys.readouterr().err
    assert code == 2
    assert "no config" in err and "capture.mjs" in err and "Traceback" not in err


def test_a_missing_cookie_says_how_to_get_one(tmp_path, capsys):
    from ronspot_sniper.cli import main

    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[ronspot]\nguid = "x"\nzone_id = 1\n'
        f'[paths]\nsession = "{tmp_path / "missing.json"}"\nstate = "{tmp_path / "s.json"}"\n'
    )

    code = main(["--config", str(cfg), "--status"])

    err = capsys.readouterr().err
    assert code == 2 and "session cookie" in err and "capture.mjs" in err


def test_a_broken_config_points_at_the_example(tmp_path, capsys):
    from ronspot_sniper.cli import main

    cfg = tmp_path / "config.toml"
    cfg.write_text("this is not toml [[[")

    assert main(["--config", str(cfg), "--status"]) == 2
    assert "config.example.toml" in capsys.readouterr().err


def test_an_unknown_notifier_is_a_message_not_a_crash(tmp_path, capsys):
    from ronspot_sniper.cli import main

    session = tmp_path / "session.json"
    session.write_text(
        '{"cookies": [{"name": "ci_session", "value": "x", "domain": "ronspot.ie"}]}'
    )
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[ronspot]\nguid = "x"\nzone_id = 1\n'
        '[notify]\nkind = "telegramme"\n'
        f'[paths]\nsession = "{session}"\nstate = "{tmp_path / "s.json"}"\n'
    )

    assert main(["--config", str(cfg), "--dry-run"]) == 2
    assert "telegramme" in capsys.readouterr().err
