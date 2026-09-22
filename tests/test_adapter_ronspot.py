"""The HTTP adapter against the real captured portal responses."""

import datetime as dt
import json

import pytest

from ronspot_sniper.adapters.ronspot import RonspotGateway
from ronspot_sniper.domain import Booking
from ronspot_sniper.ports import BookingGateway, RateLimited, SessionExpired, Unreachable
from tests.fakes import FakeTransport, fixture

GUID = "00000000-0000-0000-0000-000000000000"
ZONE = 1234
CLAIM_TOKEN = json.loads(fixture("claim_ok.json"))["ronspot_token"]
WEEK_OPEN_TOKEN = json.loads(fixture("week_open.json"))["ronspot_token"]


def build(transport: FakeTransport) -> RonspotGateway:
    return RonspotGateway(
        {"ci_session": "x"}, GUID, ZONE, transport=transport, sleep=lambda _: None
    )


def test_the_adapter_satisfies_the_port():
    assert isinstance(build(FakeTransport()), BookingGateway)


def test_week_parses_the_real_calendar():
    week = build(FakeTransport(weeks={"2026-09-28": "week_full.json"})).week(dt.date(2026, 9, 28))

    assert [d.date.isoformat() for d in week.days][:2] == ["2026-09-28", "2026-09-29"]
    tuesday = week.days[1]
    assert tuesday.mine and tuesday.spot_id == 25219 and tuesday.bay == "22 Nivel 4"
    assert not week.days[0].mine and week.days[0].bay == ""


def test_the_calendar_availability_is_recorded_but_never_decides():
    """week_open claims six free days; that is the field that proved untrue."""
    days = (
        build(FakeTransport(weeks={"2026-10-05": "week_open.json"})).week(dt.date(2026, 10, 5)).days
    )

    assert sum(d.calendar_says_free for d in days) == 6
    assert all(d.worth_trying for d in days)


def test_bookable_is_true_only_when_ronspot_offers_a_vehicle():
    gateway = build(FakeTransport(bookable={"2026-09-30"}))

    assert gateway.bookable(dt.date(2026, 9, 30))
    assert not gateway.bookable(dt.date(2026, 10, 8))


def test_claim_sends_exactly_what_the_browser_sent():
    transport = FakeTransport(weeks={"2026-10-05": "week_open.json"})
    gateway = build(transport)
    gateway.week(dt.date(2026, 10, 5))

    result = gateway.claim(dt.date(2026, 10, 8))

    assert result.accepted and result.message == "Success"
    assert transport.body("claimSpot") == {
        "booking_date": "2026-10-08",
        "CollegesGuID": GUID,
        "day_no": "8",
        "car_park_id": str(ZONE),
        "VehicleTypeId": "2",
        "VehicleFuelId": "2",
        "VehicleAccessibleId": "",
        "VehicleShareableId": "",
        "ronspot_token": WEEK_OPEN_TOKEN,
    }


def test_claim_fetches_a_token_when_it_has_none():
    transport = FakeTransport(weeks={"2026-10-05": "week_open.json"})

    build(transport).claim(dt.date(2026, 10, 8))

    assert transport.paths()[0].endswith("Claim_release")


def test_claim_rotates_the_token_for_the_next_call():
    transport = FakeTransport(weeks={"2026-10-05": "week_open.json"})
    gateway = build(transport)
    gateway.week(dt.date(2026, 10, 5))
    gateway.claim(dt.date(2026, 10, 8))

    gateway.claim(dt.date(2026, 10, 15))

    second = [f for p, f in transport.calls if p.endswith("claimSpot")][1]
    assert second["ronspot_token"] == CLAIM_TOKEN


def test_confirm_waits_for_the_queue_then_returns_the_bay():
    transport = FakeTransport(pending=["pending_wait.json", "pending_wait.json", "pending_ok.json"])

    booking = build(transport).confirm(dt.date(2026, 10, 5))

    assert booking == Booking(dt.date(2026, 10, 5), 25228, "11 Nivel 3")


def test_confirm_gives_up_when_ronspot_never_confirms():
    transport = FakeTransport(pending=["pending_wait.json"])

    assert build(transport).confirm(dt.date(2026, 10, 5), tries=3) is None


def test_release_hands_the_booking_back():
    transport = FakeTransport()

    assert build(transport).release(Booking(dt.date(2026, 10, 5), 25228, "11 Nivel 3"))
    assert transport.body("releaseAssignSpot")["SpotID"] == "25228"


def test_an_expired_cookie_is_told_apart_from_a_real_answer():
    with pytest.raises(SessionExpired):
        build(FakeTransport(weeks={"2026-09-28": "login.html"})).week(dt.date(2026, 9, 28))


@pytest.mark.parametrize("status", [401, 403, 429])
def test_rate_limits_surface_as_their_own_error(status):
    with pytest.raises(RateLimited) as caught:
        build(FakeTransport(status=status)).week(dt.date(2026, 9, 28))
    assert caught.value.status == status


def test_a_server_error_is_not_a_crash():
    """A 500 used to break the tick with a traceback and leave the state unsaved."""
    with pytest.raises(Unreachable):
        build(FakeTransport(status=500)).week(dt.date(2026, 9, 28))


def test_a_network_outage_has_its_own_error():
    """The router reboots at 04:00; that is neither Ronspot's fault nor the cookie's."""
    with pytest.raises(Unreachable):
        build(FakeTransport(offline=True)).week(dt.date(2026, 9, 28))


def test_the_vehicle_check_also_survives_the_outage():
    with pytest.raises(Unreachable):
        build(FakeTransport(offline=True)).bookable(dt.date(2026, 9, 28))


def test_a_login_page_on_the_vehicle_check_is_not_read_as_availability():
    """Without the sentinel, an HTML page carrying any <select> counted as a free spot."""
    html = '<!DOCTYPE html><select id="lang"><option>es</option></select><form id="login-form">'

    with pytest.raises(SessionExpired):
        build(FakeTransport(vehicles_body=html)).bookable(dt.date(2026, 9, 30))


def test_a_rate_limit_on_the_vehicle_check_is_told_apart():
    with pytest.raises(RateLimited):
        build(FakeTransport(vehicles_status=429)).bookable(dt.date(2026, 9, 30))


def test_an_unreadable_day_is_skipped_instead_of_killing_the_week():
    from ronspot_sniper.adapters.ronspot.parsing import parse_day

    assert parse_day({"Full_Date": "not-a-date"}) is None
    assert parse_day({"Spotavailable": 1}) is None
    assert parse_day({"Full_Date": "2026-09-30"}) is not None
