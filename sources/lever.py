"""Lever job board source (public JSON API, no scraping)."""

from . import Job, fetch_json

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


def fetch(company: str):
    """Return a list of Jobs for a Lever company, or None if the fetch failed."""
    data = fetch_json(API_URL.format(company=company))
    if data is None:
        return None
    if not isinstance(data, list):  # Lever returns a bare JSON array
        return None

    jobs = []
    for p in data:
        categories = p.get("categories") or {}
        location = (categories.get("location") or "").strip()
        # Lever marks remote roles via workplaceType; surface that in the
        # location string so the "Remote" location filter can catch it.
        if (p.get("workplaceType") or "").lower() == "remote" and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()

        jobs.append(Job(
            id=f"lever:{p['id']}",
            source="lever",
            company=company,
            title=(p.get("text") or "").strip(),
            location=location,
            url=p.get("hostedUrl") or "",
        ))
    return jobs
