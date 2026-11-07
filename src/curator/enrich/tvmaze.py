"""TVmaze (no key): find the show by tvdb/imdb id, read latest + next episode."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from curator.enrich.net import Fetch
from curator.model import Enrichment, EpisodeRef

API = "https://api.tvmaze.com"


def add_episodes(fetch: Fetch, show: Enrichment) -> Enrichment:
    """Fill tvmaze_id, status, latest and upcoming episode. Unchanged if TVmaze lacks it."""
    maze_id = find_id(fetch, show)
    if maze_id is None:
        return show
    data = fetch(f"{API}/shows/{maze_id}?embed[]=nextepisode&embed[]=previousepisode") or {}
    embedded = data.get("_embedded") or {}
    return replace(
        show,
        tvmaze_id=maze_id,
        show_status=data.get("status"),
        latest=episode_ref(embedded.get("previousepisode")),
        upcoming=episode_ref(embedded.get("nextepisode")),
    )


def find_id(fetch: Fetch, show: Enrichment) -> int | None:
    """Look up by id, never by title (titles collide across US/UK remakes)."""
    queries = [("thetvdb", show.tvdb_id), ("imdb", show.imdb_id)]
    for field, value in queries:
        if not value:
            continue
        found = fetch(f"{API}/lookup/shows?{field}={value}")
        if isinstance(found, dict) and found.get("id"):
            return int(found["id"])
    return None


def episode_ref(raw: Any) -> EpisodeRef | None:
    if not isinstance(raw, dict) or raw.get("season") is None or raw.get("number") is None:
        return None
    return EpisodeRef(int(raw["season"]), int(raw["number"]), raw.get("airdate") or None)
