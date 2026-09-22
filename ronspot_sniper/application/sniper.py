"""One tick: read the weeks that matter, and take whatever is free."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from ..domain import Booking, Day, SniperConfig, policy
from ..domain.state import State
from ..ports import BookingGateway, Notifier, RateLimited, SessionExpired, Unreachable
from .report import SESSION_EXPIRED, spots_taken

log = logging.getLogger(__name__)

CONFIRM_TRUST_SECONDS = 900.0
"""A booking I just confirmed outranks the calendar: Ronspot's queue is asynchronous and
the calendar lags behind it. Without this, a sweep forgets the booking and asks for it
again, which ends in a rejection and a phone notification."""


@dataclass
class TickReport:
    polled_weeks: int = 0
    booked: list[Booking] = field(default_factory=list)
    failed: list[tuple[dt.date, str]] = field(default_factory=list)
    mine: list[Day] = field(default_factory=list)
    phantom: list[dt.date] = field(default_factory=list)
    stopped: str = ""


def run_tick(
    gateway: BookingGateway,
    state: State,
    notifier: Notifier,
    config: SniperConfig,
    *,
    today: dt.date,
    now: float,
    dry_run: bool = False,
    full_sweep: bool = False,
    include_today: bool = True,
) -> TickReport:
    report = TickReport()
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
            days.extend(gateway.week(start).days)
            report.polled_weeks += 1
    except RateLimited as exc:
        delay = state.penalise(now)
        report.stopped = f"rate limit {exc.status}: paused {delay / 60:.0f} min"
        log.warning(report.stopped)
        return report
    except Unreachable as exc:
        report.stopped = "no network"
        log.debug("no network while reading the calendar: %s", exc)
        return report
    except SessionExpired:
        report.stopped = "session expired"
        if not state.session_alert_sent:
            # Only counts as warned if the notifier accepted it; otherwise we retry next
            # tick. This is the one alert the Ronspot app cannot give you.
            state.session_alert_sent = notifier.send(SESSION_EXPIRED)
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
            if not gateway.bookable(day.date):
                report.phantom.append(day.date)
                continue
            if dry_run:
                report.booked.append(Booking(day.date, 0, "dry run"))
                continue
            claim = gateway.claim(day.date)
            if not claim.accepted:
                state.rejected[key] = state.rejected.get(key, 0) + 1
                report.failed.append((day.date, claim.message or "rejected without a reason"))
                continue
            booking = gateway.confirm(day.date, tries=config.confirm_tries, gap=config.confirm_gap)
        except RateLimited as exc:
            delay = state.penalise(now)
            report.stopped = f"rate limit {exc.status} while booking: paused {delay / 60:.0f} min"
            break
        except Unreachable:
            report.stopped = "no network"
            break
        except SessionExpired:
            report.stopped = "session expired"
            break
        if booking is None:
            state.rejected[key] = state.rejected.get(key, 0) + 1
            report.failed.append((day.date, "queued, Ronspot never confirmed it"))
            continue
        state.rejected.pop(key, None)
        state.covered[key] = booking.bay
        state.confirmed_at[key] = now
        report.booked.append(booking)

    if not report.stopped:
        state.relax()
    if report.booked and not dry_run:
        notifier.send(spots_taken(report.booked))
    return report
