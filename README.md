# ronspot-sniper

Watches your [Ronspot](https://ronspotflexwork.com/) calendar and books a parking spot on
the days you want, the moment somebody releases one. Built to run from cron on a Raspberry
Pi: one tick per minute, and complete silence while nothing happens.

This is not an official client. It talks to the employee portal the same way your browser
does.

## Why `Spotavailable` is not enough

If you are going to touch this, here is what saves you the night it cost me:

- **There is a booking window** (14 days in my zone; measure yours with `--status`).
  **Outside it, Ronspot marks every day as available**, weekends included, and lets you
  book none of them. Trusting `Spotavailable` ends in rejected bookings.
- **The signal that works is `GetAvalablevehicleTypeDayWise`**: it only returns an
  `<option>` with your plate when the day is genuinely bookable. That is
  `RonspotClient.bookable()`, and it is the only thing allowed to trigger a booking.
- **Booking is asynchronous.** `claimSpot` answers `"In Process"`; the booking is only
  real once `getPendingClaimStatus` returns `isClaimSuccessful: 1`.
- **`isClaimPendingRequest: 1` does not mean "I have one queued"**, it means "this day is
  not yours". It shows up on dates you never asked for.
- **Ronspot's clock runs in Dublin**, not in your country. Dates are computed in its zone;
  the cut-off time, in yours (`local_tz`).

## Getting started

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+ and a Ronspot account.

```sh
git clone https://github.com/Endika/ronspot-sniper && cd ronspot-sniper
make install
npm install
```

The login is behind reCAPTCHA v3, so **it cannot be automated**. You sign in once:

```sh
node tools/capture.mjs ~/.ronspot
```

A Chromium window opens. Sign in, open your car park calendar, move a week or two forward,
and close the window. On close you get, in `~/.ronspot`:

- `session.json` — the session cookie
- `config.toml` — your GUID, car park and vehicle, already filled in

Your password and the reCAPTCHA token are redacted before anything touches disk.

Set `weekdays` and `giveup_time`, then check it sees you correctly:

```sh
make status
```

## Usage

```sh
make tick      # one tick
make dry-run   # look, don't book
make status    # what I have, what's missing
make report    # send that summary
```

They read `~/.ronspot/config.toml`; point them elsewhere with `make status CONFIG=path`.

With nothing to report it prints nothing and notifies nobody. That is deliberate: it runs
every minute.

## Layout

Ports and adapters, with the decisions kept away from the plumbing:

```
domain/       models and policy — pure, no network, no files, no clock
ports/        BookingGateway and Notifier: the two real boundaries
adapters/     ronspot/ (HTTP), notify/ (console, slack, discord), state/ (JSON)
application/  the tick use case and the wording of reports
cli/          argparse and the composition root
```

The dependency arrow only ever points inwards: `application` knows the ports, never
`requests`. That is what lets the use-case tests run against an in-memory car park while
the adapter tests replay real captured responses.

Two things deliberately left out: there is no `Clock` port, because `run_tick` already
takes `today` and `now` as arguments; and no repository or aggregate layer, because a
tool with one integration and no invariants gets nothing from it but indirection.

## Configuration

See [`config.example.toml`](config.example.toml). The ones you will actually touch:

| Option | What it does |
|---|---|
| `weekdays` | Which days you want. `0` = Monday; `[1, 3]` = Tuesday and Thursday |
| `horizon_days` | How far ahead your Ronspot lets you book |
| `giveup_time` | After this hour the current day is dropped. `""` disables it |
| `local_tz` | Your clock, for that cut-off |
| `resync_minutes` | How often it re-reads the whole window and keeps the cookie alive |

## Notifications: Slack, Discord, or one you write

The core only knows one port, `Notifier.send(text)`. Adapters live in
`ronspot_sniper/adapters/notify/` and are picked from config.

**Slack** — needs a bot with `chat:write`. With `chat:write.public` it also posts to any
public channel without being invited. `channel` is the ID, not the name: take it from the
channel URL, after `/archives/`.

```toml
[notify]
kind = "slack"

[notify.slack]
token = "xoxb-..."
channel = "C01AB2CD3EF"
```

**Discord** — just a webhook URL. No bot, no permissions: Edit channel → Integrations →
Webhooks → New webhook.

```toml
[notify]
kind = "discord"

[notify.discord]
webhook = "https://discord.com/api/webhooks/..."
```

**Console** (`kind = "console"`) is the default when nothing is configured: notifications
go to stdout and, from cron, end up in the log.

**To add your own** (Telegram, ntfy, email…):

1. Create `ronspot_sniper/adapters/notify/telegram.py` with a class exposing
   `from_options(options) -> Telegram | None` and `send(text) -> bool`.
2. Register it in `ADAPTERS` inside `adapters/notify/__init__.py`.
3. Its config section is `[notify.telegram]`, handed to `from_options` untouched.

If your adapter is missing the data it needs, `from_options` returns `None` and
notifications fall back to the console: a misconfigured notifier must never stop you
getting the spot.

## What reaches you

1. **Spot taken** — immediately. Several in the same minute go in a single message.
2. **Session expired** — once, and only once. The one alert the Ronspot app cannot give you.
3. **Daily report** — what you have and what is missing, if you schedule `--report`.
4. **Stopped** — that same report when something is broken, instead of the list.

## Cron

```
* * * * * cd ~/ronspot-sniper && flock -n /tmp/ronspot.lock .venv/bin/python -m ronspot_sniper --config ~/.ronspot/config.toml >> ~/.ronspot/sniper.log 2>&1
0 8 * * * cd ~/ronspot-sniper && flock -w 120 /tmp/ronspot.lock .venv/bin/python -m ronspot_sniper --config ~/.ronspot/config.toml --report >> ~/.ronspot/sniper.log 2>&1
0 5 * * * [ -f ~/.ronspot/sniper.log ] && [ $(stat -c%s ~/.ronspot/sniper.log) -gt 1048576 ] && : > ~/.ronspot/sniper.log
```

The log stays empty while nothing happens; the third line truncates it if a long Ronspot
outage makes it grow.

## How much it bothers Ronspot

A tick only requests the weeks holding a target day that is not yours yet. If none are
missing, **it makes no request at all**.

| Situation | Requests per minute |
|---|---|
| Everything booked | 0 |
| One day pending | 2 |
| Re-sync, every 30 min | 3 |

On a 429 or a 403 it backs off on its own, exponentially from 5 minutes to 2 hours.

## Re-seeding the cookie

When the session expires you get one alert. Then:

```sh
node tools/capture.mjs ~/.ronspot
```

## Quality gates

```sh
make check    # lint, format, types and tests; `make format` fixes what it can
```

Tests run against an in-memory Ronspot fed with real, anonymised portal responses in
`tests/fixtures/`. If you deploy to a machine with a different Python, run the suite there
too.

## What this stores, and where

- **Your Ronspot session cookie**, in `session.json`. It is equivalent to being inside
  your account: anyone holding it can see and change your bookings. Written `600`, and it
  must **never** reach git.
- **Your Slack token or Discord webhook**, in `config.toml`. Same treatment.
- `config.toml`, `session.json` and `state.json` are in `.gitignore`. Check with
  `git status` before your first commit.

Your password is **never stored**: `tools/capture.mjs` redacts it, along with the
reCAPTCHA token, before writing anything to disk.

`tests/fixtures/` are real portal responses, anonymised: GUID zeroed, plate `TESTPLATE`,
names and emails replaced, zone ids changed. If you add fixtures, run the same scissors
over them before committing.

Security issues go through the [Security tab](https://github.com/Endika/ronspot-sniper/security),
not a public issue.

## Limitations

- The login cannot be automated (reCAPTCHA v3): the cookie is seeded by hand.
- Tested against a single Ronspot installation. `horizon_days` and the vehicle ids may not
  match yours; `--status` and `--dry-run` will tell you.
- A booking being accepted is not up to this script alone: if someone beats you to it,
  Ronspot rejects it and the next tick tries again.

## Language

Code, comments and docs are in English. Commit messages are in Spanish.

## License

MIT. See [LICENSE](LICENSE).
