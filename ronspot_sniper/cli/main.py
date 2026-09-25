from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

from ..adapters.notify import Console, UnknownNotifier
from ..adapters.notify import build as build_notifier
from ..adapters.ronspot import RonspotGateway
from ..adapters.state import load_state, save_state
from ..application import TickReport, daily_summary, pretty_date, run_tick
from ..config import DEFAULT_CONFIG, Settings, load_cookies
from ..domain import policy
from ..ports import BookingGateway, Notifier

RONSPOT_TZ = ZoneInfo("Europe/Dublin")
"""Ronspot is Irish and its clock runs in Dublin: the capture shows `date: 2026-09-22`
next to `zone_current_time: 00:25` while the Pi in Madrid read 01:25. Using the local
date would shift the whole window by a day between midnight and 1am."""


def build_gateway(settings: Settings) -> BookingGateway:
    cfg = settings.gateway
    return RonspotGateway(
        load_cookies(cfg.session_path),
        cfg.guid,
        cfg.zone_id,
        base_url=cfg.base_url,
        vehicle_type_id=cfg.vehicle_type_id,
        vehicle_fuel_id=cfg.vehicle_fuel_id,
    )


def notifier_for(settings: Settings) -> Notifier:
    return build_notifier(settings.notify_kind, settings.notify_options)


def bail(*lines: str) -> int:
    """A setup problem deserves one sentence, not a twelve-line traceback."""
    print(f"ronspot-sniper: {lines[0]}", file=sys.stderr)
    for extra in lines[1:]:
        print(f"  {extra}", file=sys.stderr)
    return 2


def print_report(report: TickReport, dry_run: bool) -> None:
    # Neither an outage nor a backoff is news: both happen every minute and would fill a
    # log that is meant to stay empty.
    if report.stopped and not report.stopped.startswith(("no network", "backoff")):
        print(f"stopped: {report.stopped}")
    for booking in report.booked:
        verb = "would book" if dry_run else "booked"
        print(f"{verb}: {pretty_date(booking.date)} — {booking.bay or 'no number'}")
    for date, why in report.failed:
        print(f"failed: {pretty_date(date)} — {why}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ronspot-sniper")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--dry-run", action="store_true", help="say what it would take, take nothing"
    )
    parser.add_argument("--status", action="store_true", help="what I hold and what is missing")
    parser.add_argument("--report", action="store_true", help="send that summary to the notifier")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        settings = Settings.load(args.config)
    except FileNotFoundError:
        return bail(
            f"no config at {args.config}",
            "generate one with:  node tools/capture.mjs ~/.ronspot",
            "or copy config.example.toml and fill it in",
        )
    except (tomllib.TOMLDecodeError, KeyError, ValueError) as exc:
        return bail(
            f"the config at {args.config} is broken: {exc}", "compare it with config.example.toml"
        )

    # Before touching the network: a misspelled destination shows up instantly.
    try:
        notifier_for(settings)
    except UnknownNotifier as exc:
        return bail(str(exc))

    state = load_state(settings.state_path)
    try:
        gateway = build_gateway(settings)
    except FileNotFoundError:
        return bail(
            f"no session cookie at {settings.gateway.session_path}",
            "generate one with:  node tools/capture.mjs",
        )
    except (KeyError, ValueError) as exc:
        return bail(f"the session cookie at {settings.gateway.session_path} is unusable: {exc}")

    today = dt.datetime.now(RONSPOT_TZ).date()
    now = time.time()
    give_up_at = settings.give_up_at
    include_today = policy.still_chasing_today(
        today, dt.datetime.now(ZoneInfo(settings.local_tz)), give_up_at
    )

    if args.status or args.report:
        report = run_tick(
            gateway,
            state,
            Console(),
            settings.sniper,
            today=today,
            now=now,
            dry_run=True,
            full_sweep=True,
            include_today=include_today,
        )
        pending = [
            d
            for d in policy.wanted_dates(
                today, settings.sniper.weekdays, settings.sniper.horizon_days
            )
            if d.isoformat() not in state.covered
        ]
        summary = daily_summary(
            report.mine,
            pending,
            state,
            today=today,
            give_up_at=give_up_at,
            include_today=include_today,
            stopped=report.stopped,
        )
        if args.report:
            notifier_for(settings).send(summary)
        print(summary)
        return 1 if report.stopped else 0

    notifier = Console() if args.dry_run else notifier_for(settings)
    report = run_tick(
        gateway,
        state,
        notifier,
        settings.sniper,
        today=today,
        now=now,
        dry_run=args.dry_run,
        include_today=include_today,
    )
    if not args.dry_run:
        save_state(state, settings.state_path)
    print_report(report, args.dry_run)
    return 0
