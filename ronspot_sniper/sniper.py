"""Un tic: mira las semanas que hagan falta y coge lo que esté libre."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from . import policy
from .client import Booking, Day, RateLimited, RonspotClient, SessionExpired, Unreachable
from .config import Config
from .notify import Notifier
from .state import State

log = logging.getLogger(__name__)

CONFIRM_TRUST_SECONDS = 900.0
"""Una reserva que acabo de confirmar manda sobre el calendario: la cola de Ronspot es
asíncrona y el calendario tarda en reflejarla. Sin esto, un barrido la olvida y la vuelve
a pedir, que acaba en rechazo y notificación al móvil."""

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def es_fecha(date: dt.date) -> str:
    return f"{DIAS[date.weekday()]} {date.day:02d}/{date.month:02d}"


@dataclass
class Report:
    polled_weeks: int = 0
    booked: list[Booking] = field(default_factory=list)
    failed: list[tuple[dt.date, str]] = field(default_factory=list)
    mine: list[Day] = field(default_factory=list)
    phantom: list[dt.date] = field(default_factory=list)
    stopped: str = ""


def _message(bookings: list[Booking]) -> str:
    if len(bookings) == 1:
        one = bookings[0]
        return f":car: Plaza cogida para el {es_fecha(one.date)} — {one.bay or 'sin número'}"
    lines = "\n".join(f"• {es_fecha(b.date)} — {b.bay or 'sin número'}" for b in bookings)
    return f":car: {len(bookings)} plazas cogidas:\n{lines}"


def run_tick(
    config: Config,
    state: State,
    client: RonspotClient,
    notifier: Notifier,
    *,
    today: dt.date,
    now: float,
    dry_run: bool = False,
    full_sweep: bool = False,
    include_today: bool = True,
) -> Report:
    report = Report()
    if state.blocked(now):
        report.stopped = "backoff"
        return report

    state.forget_past(today)
    sweep = full_sweep or (now - state.last_sweep) >= config.resync_seconds
    starts = (
        policy.week_starts(today, config.horizon_days)
        if sweep
        else policy.weeks_to_poll(
            today, config.weekdays, state.covered_dates(), config.horizon_days, include_today
        )
    )
    if not starts:
        return report

    days: list[Day] = []
    try:
        for start in starts:
            days.extend(client.week(start).days)
            report.polled_weeks += 1
    except RateLimited as exc:
        delay = state.penalise(now)
        report.stopped = f"rate limit {exc.status}: parado {delay / 60:.0f} min"
        log.warning(report.stopped)
        return report
    except Unreachable as exc:
        report.stopped = "sin red"
        log.debug("sin red al mirar el calendario: %s", exc)
        return report
    except SessionExpired:
        report.stopped = "sesión caducada"
        if not state.session_alert_sent:
            # Solo se da por avisado si Slack lo aceptó; si no, se reintenta al tic
            # siguiente. Es el único aviso que la app de Ronspot no puede darte.
            state.session_alert_sent = notifier.send(
                ":lock: Ronspot: la sesión ha caducado y el cazador está ciego. "
                "Re-siémbrala con `node tools/capture.mjs`."
            )
        return report

    state.session_alert_sent = False
    mine = policy.already_mine(days, config.weekdays, today, config.horizon_days)
    report.mine = mine
    if sweep:
        state.last_sweep = now
        fresh = {d.date.isoformat(): d.bay for d in mine}
        for key, when in state.confirmed_at.items():
            if now - when < CONFIRM_TRUST_SECONDS:
                fresh.setdefault(key, state.covered.get(key, ""))
        state.covered = fresh
    else:
        state.covered.update({d.date.isoformat(): d.bay for d in mine})

    for day in policy.candidates(days, config.weekdays, today, config.horizon_days, include_today):
        key = day.date.isoformat()
        if key in state.covered:
            continue
        try:
            if not client.bookable(day.date):
                report.phantom.append(day.date)
                continue
        except RateLimited as exc:
            delay = state.penalise(now)
            report.stopped = (
                f"rate limit {exc.status} al mirar el coche: parado {delay / 60:.0f} min"
            )
            break
        except Unreachable:
            report.stopped = "sin red"
            break
        except SessionExpired:
            report.stopped = "sesión caducada al mirar el coche"
            break
        if dry_run:
            report.booked.append(Booking(day.date, 0, "(en seco)"))
            continue
        try:
            ok, message = client.claim(day.date)
            if not ok:
                state.rejected[key] = state.rejected.get(key, 0) + 1
                report.failed.append((day.date, message or "rechazada sin motivo"))
                continue
            booking = client.confirm(day.date, tries=config.confirm_tries, gap=config.confirm_gap)
        except RateLimited as exc:
            delay = state.penalise(now)
            report.stopped = f"rate limit {exc.status} al reservar: parado {delay / 60:.0f} min"
            break
        except Unreachable:
            report.stopped = "sin red al reservar"
            break
        except SessionExpired:
            report.stopped = "sesión caducada al reservar"
            break
        if booking is None:
            state.rejected[key] = state.rejected.get(key, 0) + 1
            report.failed.append((day.date, "encolada, Ronspot no la ha confirmado"))
            continue
        state.rejected.pop(key, None)
        state.covered[key] = booking.bay
        state.confirmed_at[key] = now
        report.booked.append(booking)

    if not report.stopped:
        state.relax()
    if report.booked and not dry_run:
        notifier.send(_message(report.booked))
    return report
