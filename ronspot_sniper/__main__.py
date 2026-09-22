from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

from . import policy
from .client import RonspotClient
from .config import DEFAULT_CONFIG, Config, load_cookies
from .notify import Console, Notifier, UnknownNotifier
from .notify import build as build_notifier
from .sniper import Report, es_fecha, run_tick
from .state import State

ZONA_RONSPOT = ZoneInfo("Europe/Dublin")
"""Ronspot es irlandés y su reloj va en Dublín: en la captura conviven `date: 2026-09-22`
y `zone_current_time: 00:25` con el Pi en Madrid a las 01:25. Usar la fecha local
desplazaría la ventana un día entero entre las 00:00 y la 01:00."""


def build_client(config: Config) -> RonspotClient:
    return RonspotClient(
        load_cookies(config.session_path),
        config.guid,
        config.zone_id,
        base_url=config.base_url,
        vehicle_type_id=config.vehicle_type_id,
        vehicle_fuel_id=config.vehicle_fuel_id,
    )


def print_report(report: Report, dry_run: bool) -> None:
    # Ni un corte de red ni un backoff son noticia: pasan cada minuto y llenarían el log.
    if report.stopped and not report.stopped.startswith(("sin red", "backoff")):
        print(f"parado: {report.stopped}")
    for booking in report.booked:
        verb = "reservaría" if dry_run else "reservada"
        print(f"{verb}: {es_fecha(booking.date)} — {booking.bay or 'sin número'}")
    for date, why in report.failed:
        print(f"fallida: {es_fecha(date)} — {why}")


def fallo(*lineas: str) -> int:
    """Un problema de instalación merece una frase, no un traceback de doce líneas."""
    print(f"ronspot-sniper: {lineas[0]}", file=sys.stderr)
    for extra in lineas[1:]:
        print(f"  {extra}", file=sys.stderr)
    return 2


def avisador(config: Config) -> Notifier:
    """El adaptador que diga el config; sin destino configurado, la consola."""
    return build_notifier(config.notify_kind, config.notify_options)


def resumen(
    report: Report,
    pending: list[dt.date],
    state: State,
    corte: dt.time | None,
    today: dt.date,
    include_today: bool,
) -> str:
    """El parte diario. Cubre el caso que no genera mensaje: no haber pillado nada."""
    if report.stopped:
        return f":warning: ronspot-sniper parado: {report.stopped}"
    mias = [f"{es_fecha(d.date)} — {d.bay or 'sin número'}" for d in report.mine]
    lineas = [":car: Parte de ronspot-sniper"]
    lineas.append("Ya son tuyos: " + (", ".join(mias) if mias else "ninguno"))
    if pending:
        falta = []
        for date in pending:
            marca = ""
            if date == today and not include_today and corte is not None:
                marca = f" (abandonado, pasadas las {corte:%H:%M})"
            fallos = state.rejected.get(date.isoformat(), 0)
            if fallos:
                marca += f" ({fallos} rechazos)"
            falta.append(f"{es_fecha(date)}{marca}")
        lineas.append("Sin pillar: " + ", ".join(falta))
    else:
        lineas.append("Sin pillar: nada, la ventana está cubierta entera")
    return "\n".join(lineas)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ronspot-sniper")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="dice qué cogería, sin cogerlo")
    parser.add_argument("--status", action="store_true", help="qué tengo y qué me falta")
    parser.add_argument("--report", action="store_true", help="manda ese resumen a Slack")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        config = Config.load(args.config)
    except FileNotFoundError:
        return fallo(
            f"no encuentro el config en {args.config}",
            "genéralo con:  node tools/capture.mjs ~/.ronspot",
            "o copia config.example.toml y rellénalo",
        )
    except (tomllib.TOMLDecodeError, KeyError, ValueError) as exc:
        return fallo(
            f"el config {args.config} está mal: {exc}", "compáralo con config.example.toml"
        )

    # Antes de tocar la red: un destino de avisos mal escrito se ve al instante.
    try:
        build_notifier(config.notify_kind, config.notify_options)
    except UnknownNotifier as exc:
        return fallo(str(exc))

    state = State.load(config.state_path)
    try:
        client = build_client(config)
    except FileNotFoundError:
        return fallo(
            f"no encuentro la cookie de sesión en {config.session_path}",
            "genérala con:  node tools/capture.mjs",
        )
    except (KeyError, ValueError) as exc:
        return fallo(f"la cookie de sesión en {config.session_path} no vale: {exc}")
    today, now = dt.datetime.now(ZONA_RONSPOT).date(), time.time()
    corte = config.giveup_time
    local_tz = ZoneInfo(config.local_tz)
    include_today = corte is None or dt.datetime.now(local_tz).time() < corte

    if args.status or args.report:
        report = run_tick(
            config,
            state,
            client,
            Console(),
            today=today,
            now=now,
            dry_run=True,
            full_sweep=True,
            include_today=include_today,
        )
        pending = [
            d
            for d in policy.wanted_dates(today, config.weekdays, config.horizon_days)
            if d.isoformat() not in state.covered
        ]
        if args.report:
            texto = resumen(report, pending, state, corte, today, include_today)
            avisador(config).send(texto)
            print(texto)
            return 0
        if report.stopped:
            print(f"parado: {report.stopped}")
            return 1
        print(f"semanas consultadas: {report.polled_weeks}")
        print("\nya son mías:")
        for day in report.mine:
            print(f"  {es_fecha(day.date)} — {day.bay or 'sin número'}")
        print("\nsin cubrir:")
        for date in pending:
            fallos = state.rejected.get(date.isoformat(), 0)
            marca = f"  ({fallos} rechazos)" if fallos else ""
            if date == today and not include_today:
                marca += f"  [abandonado, pasadas las {corte:%H:%M}]"
            print(f"  {es_fecha(date)}{marca}")
        return 0

    notifier = Console() if args.dry_run else avisador(config)
    report = run_tick(
        config,
        state,
        client,
        notifier,
        today=today,
        now=now,
        dry_run=args.dry_run,
        include_today=include_today,
    )
    if not args.dry_run:
        state.save(config.state_path)
    print_report(report, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
