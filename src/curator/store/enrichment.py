"""Store what the enricher found. Shows expire fast (new episodes), movies slowly."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from curator.model import Enrichment, EpisodeRef, Lookup

HOURS_UNTIL_STALE = {"tv": 12, "movie": 30 * 24}
HOURS_UNTIL_RETRY_NOT_FOUND = 3 * 24

_COLUMNS = (
    "media_key, kind, title, tmdb_id, release_year, imdb_id, tvdb_id, tvmaze_id, "
    "overview_sanitized, genres_json, poster_path, show_status, latest_season, latest_episode, "
    "latest_air_date, next_season, next_episode, next_air_date"
)


def due_lookups(conn: sqlite3.Connection, now: datetime) -> list[Lookup]:
    """Library titles never looked up, or looked up too long ago."""
    rows = conn.execute(
        """SELECT li.media_key, MIN(li.stream_kind), MIN(li.parsed_title), MAX(li.parsed_year)
           FROM library_items li LEFT JOIN enrichment_cache e ON e.media_key = li.media_key
           WHERE li.stream_kind IN ('movie', 'episode')
             AND (e.media_key IS NULL OR e.expires_at <= ?)
           GROUP BY li.media_key ORDER BY li.media_key""",
        (_iso(now),),
    )
    return [
        Lookup(key, "tv" if kind == "episode" else "movie", title, year)
        for key, kind, title, year in rows
    ]


def save_enrichment(conn: sqlite3.Connection, e: Enrichment, now: datetime) -> None:
    hours = HOURS_UNTIL_STALE[e.kind] if e.found else HOURS_UNTIL_RETRY_NOT_FOUND
    latest, upcoming = _episode_cols(e.latest), _episode_cols(e.upcoming)
    values = (
        *(e.media_key, e.kind, e.title, e.tmdb_id, e.year, e.imdb_id, e.tvdb_id, e.tvmaze_id),
        *(e.overview, json.dumps(list(e.genres)), e.poster_path, e.show_status),
        *latest,
        *upcoming,
        _iso(now),
        _iso(now + timedelta(hours=hours)),
    )
    with conn:
        conn.execute(
            f"INSERT OR REPLACE INTO enrichment_cache ({_COLUMNS}, fetched_at, expires_at) "
            f"VALUES ({', '.join('?' * len(values))})",
            values,
        )


def enrichments(conn: sqlite3.Connection) -> list[Enrichment]:
    """Everything known about titles still in the library, by title."""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM enrichment_cache "
        "WHERE media_key IN (SELECT media_key FROM library_items) ORDER BY lower(title)"
    )
    return [_from_row(row) for row in rows]


def _from_row(row: tuple[Any, ...]) -> Enrichment:
    key, kind, title, tmdb_id, year, imdb_id, tvdb_id, tvmaze_id = row[:8]
    overview, genres, poster, status = row[8:12]
    return Enrichment(
        key,
        kind,
        title,
        tmdb_id=tmdb_id,
        year=year,
        imdb_id=imdb_id,
        tvdb_id=tvdb_id,
        tvmaze_id=tvmaze_id,
        overview=overview,
        genres=tuple(json.loads(genres)),
        poster_path=poster,
        show_status=status,
        latest=_episode(row[12:15]),
        upcoming=_episode(row[15:18]),
    )


def _episode_cols(ref: EpisodeRef | None) -> tuple[int | None, int | None, str | None]:
    return (ref.season, ref.episode, ref.air_date) if ref else (None, None, None)


def _episode(cols: tuple[Any, ...]) -> EpisodeRef | None:
    season, episode, air_date = cols
    return EpisodeRef(season, episode, air_date) if season is not None else None


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
