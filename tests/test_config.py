import json
import stat
from pathlib import Path

from ronspot_sniper.config import load_cookies, save_cookies


def storage_state(tmp_path: Path, **ronspot: str) -> Path:
    path = tmp_path / "session.json"
    cookies = [{"name": k, "value": v, "domain": "my.ronspot.ie"} for k, v in ronspot.items()]
    cookies.append({"name": "_GRECAPTCHA", "value": "g", "domain": "www.google.com"})
    path.write_text(json.dumps({"cookies": cookies, "origins": []}))
    path.chmod(0o600)
    return path


def test_a_rotated_session_replaces_the_old_one_and_keeps_the_rest(tmp_path):
    """Without this every tick replays the seeded cookie, and Ronspot drops it in a day."""
    path = storage_state(tmp_path, ci_session="old", csrf_cookie="c")

    assert save_cookies(path, {"ci_session": "new", "csrf_cookie": "c"})

    assert load_cookies(path) == {"ci_session": "new", "csrf_cookie": "c"}
    raw = json.loads(path.read_text())
    assert raw["origins"] == [] and any(c["name"] == "_GRECAPTCHA" for c in raw["cookies"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_an_unchanged_session_is_not_rewritten(tmp_path):
    path = storage_state(tmp_path, ci_session="same")
    before = path.stat().st_mtime_ns

    assert not save_cookies(path, {"ci_session": "same"})
    assert path.stat().st_mtime_ns == before


def test_only_the_cookies_the_seed_had_are_updated(tmp_path):
    path = storage_state(tmp_path, ci_session="old")

    save_cookies(path, {"ci_session": "new", "stray": "x"})

    assert load_cookies(path) == {"ci_session": "new"}
