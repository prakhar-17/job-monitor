"""Ashby job board source (public posting API, no scraping)."""

from . import Job, fetch_json

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{name}"


def fetch(board_name: str):
    """Return a list of Jobs for an Ashby board, or None if the fetch failed."""
    data = fetch_json(API_URL.format(name=board_name))
    if data is None:
        return None

    jobs = []
    for j in data.get("jobs", []):
        location = (j.get("location") or "").strip()
        # Fold secondary locations into the string so the location filter can
        # match roles whose NY/Remote office isn't the primary listing.
        secondary = [s.get("location", "") for s in (j.get("secondaryLocations") or [])]
        secondary = [s for s in secondary if s]
        if secondary:
            location = "; ".join([location] + secondary) if location else "; ".join(secondary)
        if j.get("isRemote") and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()

        jobs.append(Job(
            id=f"ashby:{j['id']}",
            source="ashby",
            company=board_name,
            title=(j.get("title") or "").strip(),
            location=location,
            url=j.get("jobUrl") or j.get("applyUrl") or "",
        ))
    return jobs
