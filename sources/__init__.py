"""Shared bits for job sources: the normalized Job dataclass and HTTP helper.

Adding a new source (e.g. Ashby) = new module in this package exposing
`fetch(token) -> list[Job] | None`, then wire it into SOURCES in monitor.py.
"""

import logging
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


@dataclass
class Job:
    id: str        # globally unique, e.g. "greenhouse:4012345"
    source: str    # "greenhouse" | "lever"
    company: str   # board/company token from config.yaml
    title: str
    location: str
    url: str


def fetch_json(url: str):
    """GET a JSON endpoint with one retry.

    Returns the parsed JSON, or None on failure (404s and network errors are
    logged, never raised, so one bad board can't abort the cycle).
    """
    for attempt in (1, 2):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                log.warning("404 from %s — check the token in config.yaml; skipping", url)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == 1:
                log.warning("Request to %s failed (%s), retrying once", url, exc)
            else:
                log.error("Request to %s failed twice, skipping: %s", url, exc)
    return None
