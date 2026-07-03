# Job Posting Monitor

Polls Greenhouse and Lever job boards (public JSON APIs, no scraping) and
sends Telegram alerts for new postings matching your keyword/location filters.

## Setup

```
pip install -r requirements.txt
```

### 1. Create the Telegram bot

1. In Telegram, message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, pick a display name and a username (must end in `bot`).
3. BotFather replies with a **bot token** like `123456789:AAF...xyz`. Save it.
4. Open a chat with your new bot and send it any message (e.g. "hi") —
   a bot cannot message you until you message it first.

### 2. Get your chat_id

After messaging your bot, open this URL in a browser (paste your token in):

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

Find `"chat":{"id":123456789,...}` in the response — that number is your
`TELEGRAM_CHAT_ID`. (If the response is empty, send the bot another message
and refresh.)

### 3. Fill in .env

```
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=123456789:AAF...xyz
TELEGRAM_CHAT_ID=123456789
```

If `.env` is missing or incomplete, the monitor still runs — it logs the
alert text as a warning instead of sending it.

### 4. Companies and filters

Everything lives in [config.yaml](config.yaml): board tokens
(`greenhouse_boards`, `lever_companies`), `include_keywords`,
`exclude_keywords`, and `location_keywords`. Comments in the file explain how
to find a company's token and how matching works. A token that 404s is
logged and skipped, never fatal.

## Running

```
python monitor.py --once                  # one polling cycle (for cron)
python monitor.py --loop --interval 30    # continuous, every 30 min ±3 min jitter
```

### First-run baseline (important)

The **first time each company is polled**, all of its current postings are
ingested silently and marked as already-alerted. You will get **zero alerts
on that run** — this is deliberate, so day one doesn't dump hundreds of
existing postings on you. Alerts only fire for jobs that appear **after** the
baseline. Adding a new company later triggers a baseline just for it.

State is kept in `jobs.db` (SQLite). Deleting it resets all baselines — the
next run will be silent again rather than re-alerting everything.

### Cron example

Run every 30 minutes:

```
*/30 * * * * cd /path/to/SCRAPPER && /usr/bin/python3 monitor.py --once >> cron.log 2>&1
```

On Windows, use Task Scheduler with action
`python D:\JOB\SCRAPPER\monitor.py --once` (start in `D:\JOB\SCRAPPER`),
or just keep `--loop` running.

Logs rotate in `monitor.log` (1 MB × 3 backups).

## Layout

```
monitor.py            entrypoint: cycle orchestration, filtering, CLI
config.py / config.yaml
db.py                 SQLite dedup + per-company baseline tracking
notify.py             Telegram formatting, batching, 429 backoff
sources/
  __init__.py         Job dataclass + HTTP helper (10s timeout, 1 retry)
  greenhouse.py       fetch(token) -> list[Job]
  lever.py            fetch(company) -> list[Job]
  ashby.py            fetch(name) -> list[Job]
```

Each source module returns normalized `Job` dataclasses; to add another
source, create a module in `sources/` with a `fetch()` and register it in
the `SOURCES` dict in `monitor.py`.
