"""TMDB: search a title, pick the right result, read its details."""

from __future__ import annotations

import urllib.parse
from typing import Any

from curator.enrich.clean import clean_text
from curator.enrich.net import Fetch
from curator.model import Enrichment, Lookup

API = "https://api.themoviedb.org/3"


class Tmdb:
    def __init__(self, fetch: Fetch, key: str) -> None:
        self._fetch = fetch
        self._key = key

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        params["api_key"] = self._key
        reply = self._fetch(f"{API}{path}?{urllib.parse.urlencode(params)}")
        return reply if isinstance(reply, dict) else {}


def match_movie(tmdb: Tmdb, lookup: Lookup) -> Enrichment:
    params: dict[str, Any] = {"query": lookup.title}
    if lookup.year:
        params["year"] = lookup.year
    best = pick(tmdb.get("/search/movie", **params).get("results"), lookup.year, "release_date")
    if best is None:
        return Enrichment(lookup.media_key, "movie", lookup.title, year=lookup.year)
    detail = tmdb.get(f"/movie/{best['id']}") or best
    return Enrichment(
        lookup.media_key,
        "movie",
        str(detail.get("title") or lookup.title),
        tmdb_id=int(best["id"]),
        year=year_of(detail.get("release_date")),
        imdb_id=detail.get("imdb_id") or None,
        overview=clean_text(detail.get("overview")),
        genres=genre_names(detail.get("genres")),
        poster_path=detail.get("poster_path"),
    )


def match_show(tmdb: Tmdb, lookup: Lookup) -> Enrichment:
    params: dict[str, Any] = {"query": lookup.title}
    if lookup.year:
        params["first_air_date_year"] = lookup.year
    best = pick(tmdb.get("/search/tv", **params).get("results"), lookup.year, "first_air_date")
    if best is None:
        return Enrichment(lookup.media_key, "tv", lookup.title, year=lookup.year)
    detail = tmdb.get(f"/tv/{best['id']}", append_to_response="external_ids") or best
    ids = detail.get("external_ids") or {}
    return Enrichment(
        lookup.media_key,
        "tv",
        str(detail.get("name") or lookup.title),
        tmdb_id=int(best["id"]),
        year=year_of(detail.get("first_air_date")),
        imdb_id=ids.get("imdb_id") or None,
        tvdb_id=ids.get("tvdb_id") or None,
        overview=clean_text(detail.get("overview")),
        genres=genre_names(detail.get("genres")),
        poster_path=detail.get("poster_path"),
    )


def pick(results: Any, year: int | None, date_field: str) -> dict[str, Any] | None:
    """First result from the right year, else the first result.

    TMDB's year filter also matches re-releases: 'Dune' + 2024 returns Dune (2021) first."""
    if not isinstance(results, list) or not results:
        return None
    same_year = [r for r in results if year and year_of(r.get(date_field)) == year]
    return dict((same_year or results)[0])


def year_of(date: Any) -> int | None:
    text = str(date or "")
    return int(text[:4]) if text[:4].isdigit() else None


def genre_names(genres: Any) -> tuple[str, ...]:
    return tuple(str(g["name"]) for g in genres or [] if isinstance(g, dict) and g.get("name"))
