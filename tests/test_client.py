import datetime as dt
import json

import pytest

from ronspot_sniper.client import RateLimited, RonspotClient, SessionExpired, Unreachable
from tests.fake import FakeRonspot, fixture

GUID = "00000000-0000-0000-0000-000000000000"
WEEK_OPEN_TOKEN = json.loads(fixture("week_open.json"))["ronspot_token"]


def build(fake: FakeRonspot) -> RonspotClient:
    return RonspotClient({"ci_session": "x"}, GUID, 1908, transport=fake)


def test_week_parses_the_real_calendar():
    fake = FakeRonspot(weeks={"2026-09-28": "week_full.json"})
    week = build(fake).week(dt.date(2026, 9, 28))

    assert [d.date.isoformat() for d in week.days][:2] == ["2026-09-28", "2026-09-29"]
    martes = week.days[1]
    assert martes.mine and martes.spot_id == 25219 and martes.bay == "22 Nivel 4"
    assert not week.days[0].mine and week.days[0].bay == ""


def test_calendar_availability_is_recorded_but_never_decides():
    """week_open dice que hay hueco 6 días; es justo el dato que resultó no ser cierto."""
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"})
    days = build(fake).week(dt.date(2026, 10, 5)).days

    assert sum(d.calendar_says_free for d in days) == 6
    assert all(d.worth_trying for d in days)


def test_bookable_is_true_only_when_ronspot_offers_a_vehicle():
    fake = FakeRonspot(bookable={"2026-09-30"})
    client = build(fake)

    assert client.bookable(dt.date(2026, 9, 30))
    assert not client.bookable(dt.date(2026, 10, 8))


def test_claim_sends_exactly_what_the_browser_sent():
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"})
    client = build(fake)
    client.week(dt.date(2026, 10, 5))

    ok, message = client.claim(dt.date(2026, 10, 8))

    assert ok and message == "Success"
    body = fake.body("claimSpot")
    assert body == {
        "booking_date": "2026-10-08",
        "CollegesGuID": GUID,
        "day_no": "8",
        "car_park_id": "1908",
        "VehicleTypeId": "2",
        "VehicleFuelId": "2",
        "VehicleAccessibleId": "",
        "VehicleShareableId": "",
        "ronspot_token": WEEK_OPEN_TOKEN,
    }


def test_claim_fetches_a_token_when_it_has_none():
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"})

    build(fake).claim(dt.date(2026, 10, 8))

    assert fake.paths()[0].endswith("Claim_release")


def test_claim_rotates_the_token_for_the_next_call():
    fake = FakeRonspot(weeks={"2026-10-05": "week_open.json"})
    client = build(fake)
    client.week(dt.date(2026, 10, 5))
    client.claim(dt.date(2026, 10, 8))

    client.claim(dt.date(2026, 10, 15))

    segundo = [f for p, f in fake.calls if p.endswith("claimSpot")][1]
    assert segundo["ronspot_token"] == "fbdfb3c7b885ace40aa4bc14721c341e"


def test_confirm_waits_for_the_queue_then_returns_the_bay():
    fake = FakeRonspot(pending=["pending_wait.json", "pending_wait.json", "pending_ok.json"])
    slept: list[float] = []

    booking = build(fake).confirm(dt.date(2026, 10, 5), gap=1.5, sleep=slept.append)

    assert booking is not None
    assert booking.spot_id == 25228 and booking.bay == "11 Nivel 3"
    assert slept == [1.5, 1.5]


def test_confirm_gives_up_when_ronspot_never_confirms():
    fake = FakeRonspot(pending=["pending_wait.json"])

    assert build(fake).confirm(dt.date(2026, 10, 5), tries=3, sleep=lambda _: None) is None


def test_expired_cookie_is_told_apart_from_a_real_answer():
    class Login(FakeRonspot):
        def post(self, url, data=None, timeout=None, **kwargs):
            from tests.fake import FakeResponse, fixture

            return FakeResponse(fixture("login.html"))

    with pytest.raises(SessionExpired):
        build(Login()).week(dt.date(2026, 9, 28))


@pytest.mark.parametrize("status", [401, 403, 429])
def test_rate_limit_surfaces_as_its_own_error(status):
    with pytest.raises(RateLimited) as caught:
        build(FakeRonspot(status=status)).week(dt.date(2026, 9, 28))
    assert caught.value.status == status


def test_a_network_outage_has_its_own_error():
    """El router se reinicia a las 04:00; no es un fallo de Ronspot ni de la cookie."""
    with pytest.raises(Unreachable):
        build(FakeRonspot(offline=True)).week(dt.date(2026, 9, 28))


def test_the_vehicle_check_also_survives_the_outage():
    with pytest.raises(Unreachable):
        build(FakeRonspot(offline=True)).bookable(dt.date(2026, 9, 28))
