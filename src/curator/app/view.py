"""Turn enrichments + progress into the plain sentences the page shows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from curator.model import Enrichment, EpisodeRef, Progress


def show_card(e: Enrichment, at: Progress | None, today: date) -> dict[str, Any]:
    return {
        "title": e.title,
        "found": e.found,
        "at": _code(at.season, at.episode) if at else "",
        "status": e.show_status or "",
        "behind": behind(at, e.latest),
        "next": _next_text(e, today),
        "genres": ", ".join(e.genres),
    }


def movie_card(e: Enrichment) -> dict[str, Any]:
    return {
        "title": e.title,
        "found": e.found,
        "year": e.year or "",
        "genres": ", ".join(e.genres),
        "overview": e.overview,
    }


def behind(at: Progress | None, latest: EpisodeRef | None) -> str:
    """'' when caught up or unknown; otherwise what has aired past the user's place."""
    if at is None or latest is None or (latest.season, latest.episode) <= (at.season, at.episode):
        return ""
    newest = _code(latest.season, latest.episode)
    if latest.season == at.season:
        n = latest.episode - at.episode
        return f"{n} newer episode{'s' if n > 1 else ''} out, up to {newest}"
    return f"A newer season is out, up to {newest}"


def _next_text(e: Enrichment, today: date) -> str:
    if not e.found:
        return ""
    if e.upcoming is None:
        return "Show has ended" if e.show_status == "Ended" else "No next episode announced"
    when = when_text(e.upcoming.air_date, today)
    return f"Next: {_code(e.upcoming.season, e.upcoming.episode)} {when}".rstrip()


def when_text(air_date: str | None, today: date) -> str:
    """'today', 'tomorrow', 'on Fri 13 Nov (in 7 days)', or '' if no date yet."""
    if not air_date:
        return "(date not announced)"
    day = date.fromisoformat(air_date)
    days = (day - today).days
    if days in (0, 1):
        return ("today", "tomorrow")[days]
    label = f"on {day:%a} {day.day} {day:%b}"
    return f"{label} (in {days} days)" if days > 1 else label


def _code(season: int, episode: int) -> str:
    return f"S{season:02d}E{episode:02d}"


def ago_text(then: datetime, now: datetime) -> str:
    """'just now', '5 minutes ago', '3 hours ago', '2 days ago'."""
    minutes = int((now - then).total_seconds() // 60)
    for size, unit in ((24 * 60, "day"), (60, "hour"), (1, "minute")):
        if minutes >= size:
            n = minutes // size
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "just now"
