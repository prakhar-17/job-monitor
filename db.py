"""SQLite persistence: seen jobs (dedup) and per-company baseline tracking."""

import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id         TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    company    TEXT NOT NULL,
    title      TEXT NOT NULL,
    location   TEXT,
    url        TEXT,
    first_seen TEXT NOT NULL,
    alerted    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS polled_companies (
    source       TEXT NOT NULL,
    company      TEXT NOT NULL,
    first_polled TEXT NOT NULL,
    PRIMARY KEY (source, company)
);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str = "jobs.db"):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def is_known(self, job_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row is not None

    def add_job(self, job, alerted: bool) -> str:
        """Insert a job; returns its first_seen timestamp."""
        first_seen = utcnow_iso()
        self.conn.execute(
            "INSERT OR IGNORE INTO jobs (id, source, company, title, location, url, first_seen, alerted)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job.id, job.source, job.company, job.title, job.location, job.url,
             first_seen, 1 if alerted else 0),
        )
        self.conn.commit()
        return first_seen

    def has_baseline(self, source: str, company: str) -> bool:
        """True if this company has been successfully polled at least once."""
        row = self.conn.execute(
            "SELECT 1 FROM polled_companies WHERE source = ? AND company = ?",
            (source, company),
        ).fetchone()
        return row is not None

    def mark_polled(self, source: str, company: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO polled_companies (source, company, first_polled) VALUES (?, ?, ?)",
            (source, company, utcnow_iso()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
