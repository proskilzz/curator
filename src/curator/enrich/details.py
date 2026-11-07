"""TMDB details + recommendations + keywords + credits for one title, in one call."""

from __future__ import annotations

from typing import Any

from curator.enrich.clean import clean_text
from curator.enrich.tmdb import Tmdb, genre_names, year_of
from curator.model import Title, TitleInfo

CREATOR_JOBS = {"Director", "Screenplay", "Writer", "Novel", "Story", "Original Story"}
MAX_KEYWORDS = 12
MAX_CREATORS = 6


def title_info(tmdb: Tmdb, kind: str, tmdb_id: int) -> TitleInfo | None:
    """None when TMDB has no such title (404)."""
    path = "movie" if kind == "movie" else "tv"
    detail = tmdb.get(f"/{path}/{tmdb_id}", append_to_response="recommendations,keywords,credits")
    if not detail.get("id"):
        return None
    recs = (detail.get("recommendations") or {}).get("results") or []
    return TitleInfo(
        _title(kind, detail, keywords(detail), creators(detail)),
        tuple(_title(kind, r) for r in recs if isinstance(r, dict) and r.get("id")),
    )


def _title(
    kind: str, raw: dict[str, Any], kws: tuple[str, ...] = (), made_by: tuple[str, ...] = ()
) -> Title:
    runtime = raw.get("runtime") or next(iter(raw.get("episode_run_time") or []), None)
    return Title(
        kind,
        int(raw["id"]),
        clean_text(str(raw.get("title") or raw.get("name") or ""), 120),
        year=year_of(raw.get("release_date") or raw.get("first_air_date")),
        overview=clean_text(raw.get("overview"), 250),
        genres=genre_names(raw.get("genres")),
        keywords=kws,
        creators=made_by,
        popularity=float(raw.get("popularity") or 0),
        vote_average=float(raw.get("vote_average") or 0),
        vote_count=int(raw.get("vote_count") or 0),
        runtime_minutes=int(runtime) if runtime else None,
        adult=bool(raw.get("adult")),
    )


def keywords(detail: dict[str, Any]) -> tuple[str, ...]:
    """Movies keep them under keywords.keywords, shows under keywords.results."""
    box = detail.get("keywords") or {}
    items = box.get("keywords") or box.get("results") or []
    return _names(items)[:MAX_KEYWORDS]


def creators(detail: dict[str, Any]) -> tuple[str, ...]:
    crew = (detail.get("credits") or {}).get("crew") or []
    makers = [c for c in crew if isinstance(c, dict) and c.get("job") in CREATOR_JOBS]
    return _names([*(detail.get("created_by") or []), *makers])[:MAX_CREATORS]


def _names(items: list[Any]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            seen.setdefault(clean_text(str(item["name"]), 60), None)
    return tuple(seen)
