"""Job posting monitor: polls Greenhouse/Lever boards, alerts via Telegram.

Usage:
    python monitor.py --once                  one polling cycle (cron-friendly)
    python monitor.py --loop --interval 30    poll every 30 min (with +/-3 min jitter)
"""

import argparse
import logging
import random
import re
import sys
import time
from logging.handlers import RotatingFileHandler

import notify
from config import load_config
from db import Database
from sources import ashby, greenhouse, lever

log = logging.getLogger("monitor")

JITTER_MINUTES = 3

# source name -> (fetch function, config attribute). Adding a source is one
# new module + one line here.
SOURCES = {
    "greenhouse": (greenhouse.fetch, "greenhouse_boards"),
    "lever": (lever.fetch, "lever_companies"),
    "ashby": (ashby.fetch, "ashby_boards"),
}


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler("monitor.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    handlers = [file_handler]
    if sys.stderr is not None:  # no console under pythonw.exe (scheduled task)
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        handlers.append(console)
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def normalize_title(title: str) -> str:
    """Lowercase, expand '&' to 'and', strip punctuation, collapse whitespace.

    'FP&A' -> 'fp and a', so it matches 'FP and A', 'FP & A', etc.
    """
    t = title.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def match_group(job, cfg):
    """Return the include-keyword group label the job matches, or None."""
    norm_title = normalize_title(job.title)
    raw_title = job.title.lower()

    group = None
    for label, spec in cfg.include_groups.items():
        if not any(normalize_title(kw) in norm_title for kw in spec["keywords"]):
            continue
        # Per-group exclude (e.g. "manager" kills Finance matches but a
        # "Product Manager, Finance" title can still be claimed by Product).
        if any(kw.lower() in raw_title for kw in spec["exclude"]):
            continue
        group = label
        break
    if group is None:
        return None
    # Excludes run on the raw lowercased title so punctuation/space-sensitive
    # patterns like "lead " keep their meaning.
    if any(kw.lower() in raw_title for kw in cfg.exclude_keywords):
        return None
    if job.location:
        loc = job.location.lower()
        if cfg.location_keywords and not any(kw.lower() in loc for kw in cfg.location_keywords):
            return None
        if any(kw.lower() in loc for kw in cfg.location_exclude_keywords):
            return None
    return group


def run_cycle(config_path: str, db_path: str) -> None:
    cfg = load_config(config_path)
    db = Database(db_path)
    new_alerts = {}  # company -> [(Job, first_seen, group)]

    try:
        for source_name, (fetch, cfg_attr) in SOURCES.items():
            for company in getattr(cfg, cfg_attr):
                try:
                    jobs = fetch(company)
                except Exception:
                    log.exception("Unexpected error fetching %s/%s, skipping", source_name, company)
                    continue
                if jobs is None:
                    # Fetch failed: don't mark polled, so a company whose very
                    # first fetch fails still gets a proper baseline later.
                    continue

                baseline = not db.has_baseline(source_name, company)
                new_count = alert_count = 0
                for job in jobs:
                    if db.is_known(job.id):
                        continue
                    new_count += 1
                    if baseline:
                        db.add_job(job, alerted=True)
                    else:
                        group = match_group(job, cfg)
                        first_seen = db.add_job(job, alerted=group is not None)
                        if group is not None:
                            new_alerts.setdefault(company, []).append((job, first_seen, group))
                            alert_count += 1
                db.mark_polled(source_name, company)

                if baseline:
                    log.info("%s/%s: baseline run, ingested %d postings silently",
                             source_name, company, new_count)
                else:
                    log.info("%s/%s: %d postings, %d new, %d match filters",
                             source_name, company, len(jobs), new_count, alert_count)
    finally:
        db.close()

    for company, jobs_with_seen in new_alerts.items():
        notify.send_message(notify.format_company_alert(company, jobs_with_seen))

    total = sum(len(v) for v in new_alerts.values())
    log.info("Cycle done: %d new matching job(s) across %d company(ies)", total, len(new_alerts))


def main() -> int:
    parser = argparse.ArgumentParser(description="Greenhouse/Lever job posting monitor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run a single polling cycle and exit")
    mode.add_argument("--loop", action="store_true", help="poll continuously")
    parser.add_argument("--interval", type=int, default=30, help="minutes between polls in --loop mode (default 30)")
    parser.add_argument("--config", default="config.yaml", help="path to config file")
    parser.add_argument("--db", default="jobs.db", help="path to SQLite database")
    args = parser.parse_args()

    setup_logging()

    if args.once:
        run_cycle(args.config, args.db)
        return 0

    log.info("Looping every %d min (±%d min jitter). Ctrl+C to stop.", args.interval, JITTER_MINUTES)
    while True:
        try:
            run_cycle(args.config, args.db)
        except Exception:
            log.exception("Cycle failed; will retry next interval")
        delay = max(60.0, args.interval * 60 + random.uniform(-JITTER_MINUTES, JITTER_MINUTES) * 60)
        log.info("Sleeping %.1f minutes", delay / 60)
        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            log.info("Stopped.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
