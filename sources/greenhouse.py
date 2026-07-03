"""Greenhouse job board source (public JSON API, no scraping)."""

from . import Job, fetch_json

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(board_token: str):
    """Return a list of Jobs for a board, or None if the fetch failed."""
    data = fetch_json(API_URL.format(token=board_token))
    if data is None:
        return None

    jobs = []
    for j in data.get("jobs", []):
        jobs.append(Job(
            id=f"greenhouse:{j['id']}",
            source="greenhouse",
            company=board_token,
            title=(j.get("title") or "").strip(),
            location=((j.get("location") or {}).get("name") or "").strip(),
            url=j.get("absolute_url") or "",
        ))
    return jobs
