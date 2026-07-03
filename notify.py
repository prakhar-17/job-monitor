"""Telegram alerts: per-company batched messages with 429 retry/backoff."""

import logging
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4096
MAX_RETRIES = 4


def _escape_md(text: str) -> str:
    """Escape Telegram legacy-Markdown special characters."""
    for ch in ("\\", "_", "*", "[", "`"):
        text = text.replace(ch, "\\" + ch)
    return text


def format_company_alert(company: str, jobs_with_seen) -> str:
    """One message per company. jobs_with_seen = [(Job, first_seen_iso, group), ...]"""
    now = datetime.now(timezone.utc)
    lines = [f"*{_escape_md(company.capitalize())}* — {len(jobs_with_seen)} new matching job(s)"]
    for job, first_seen, group in jobs_with_seen:
        minutes = max(0, int((now - datetime.fromisoformat(first_seen)).total_seconds() // 60))
        location = job.location or "location not listed"
        tag = f"\\[{_escape_md(group)}] " if group else ""
        lines.append(f"• {tag}[{_escape_md(job.title)}]({job.url}) — {location} — first seen {minutes} min ago")
    return "\n".join(lines)


def _split_message(text: str):
    """Split on line boundaries so we never exceed Telegram's 4096-char limit."""
    if len(text) <= MAX_MESSAGE_LEN:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > MAX_MESSAGE_LEN:
            if current:
                chunks.append(current)
            current = line[:MAX_MESSAGE_LEN]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def send_message(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env). "
                    "Message that would have been sent:\n%s", text)
        return False

    ok = True
    for chunk in _split_message(text):
        ok = _send_chunk(token, chat_id, chunk) and ok
    return ok


def _send_chunk(token: str, chat_id: str, text: str) -> bool:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(API_URL.format(token=token), json=payload, timeout=10)
        except requests.RequestException as exc:
            log.warning("Telegram request failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            try:
                retry_after = int(resp.json()["parameters"]["retry_after"])
            except (ValueError, KeyError, TypeError):
                retry_after = 2 ** attempt
            log.warning("Telegram rate limit hit, retrying in %ds", retry_after)
            time.sleep(retry_after)
            continue

        if resp.ok:
            return True

        log.error("Telegram send failed (%d): %s", resp.status_code, resp.text[:300])
        return False

    log.error("Telegram send gave up after %d attempts", MAX_RETRIES)
    return False
