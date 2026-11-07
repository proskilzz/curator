"""SQLite: open the database, save one scan. The only module that runs SQL."""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from curator.model import Episode, Parsed, Progress
from curator.progress import advance


@dataclass
class ScanCounts:
    new: int = 0
    seen_again: int = 0
    missing: int = 0
    shows_advanced: list[str] = field(default_factory=list)


def default_db_path() -> Path:
    return Path.home() / "Library" / "Application Support" / "Curator" / "curator.db"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(files("curator.store").joinpath("schema.sql").read_text())
    return conn


def save_scan(conn: sqlite3.Connection, root: Path, items: Iterable[Parsed]) -> ScanCounts:
    """Record one scan of `root`: add/refresh files, mark vanished ones, move progress forward."""
    counts = ScanCounts()
    known = _known_paths(conn, root)
    seen: set[str] = set()
    new_episodes: dict[str, list[Episode]] = defaultdict(list)
    titles: dict[str, str] = {}
    with conn:
        for item in items:
            seen.add(item.file.path)
            if item.file.path in known:
                _refresh(conn, item)
                counts.seen_again += 1
                continue
            _insert(conn, item)
            counts.new += 1
            if isinstance(item.media, Episode):
                new_episodes[item.media_key].append(item.media)
                titles[item.media_key] = item.title
        counts.missing = _mark_missing(conn, known - seen)
        for key, episodes in new_episodes.items():
            if _advance_show(conn, key, titles[key], episodes):
                counts.shows_advanced.append(titles[key])
    return counts


def _known_paths(conn: sqlite3.Connection, root: Path) -> set[str]:
    prefix = str(root).rstrip(os.sep) + os.sep
    rows = conn.execute("SELECT file_path FROM library_items")
    return {path for (path,) in rows if path.startswith(prefix)}


def _insert(conn: sqlite3.Connection, item: Parsed) -> None:
    media = item.media
    season = media.season if isinstance(media, Episode) else None
    episode = media.episode if isinstance(media, Episode) else None
    year = None if isinstance(media, Episode) else media.year
    conn.execute(
        """INSERT INTO library_items (file_path, file_name, file_size_bytes, file_mtime,
               stream_kind, media_key, parsed_title, parsed_year, season_number,
               episode_number, resolution, video_codec)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item.file.path,
            item.file.name,
            item.file.size_bytes,
            item.file.mtime,
            item.kind,
            item.media_key,
            item.title,
            year,
            season,
            episode,
            item.resolution,
            item.video_codec,
        ),
    )


def _refresh(conn: sqlite3.Connection, item: Parsed) -> None:
    conn.execute(
        """UPDATE library_items SET file_size_bytes = ?, file_mtime = ?, is_present_on_disk = 1,
               last_seen_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
           WHERE file_path = ?""",
        (item.file.size_bytes, item.file.mtime, item.file.path),
    )


def _mark_missing(conn: sqlite3.Connection, paths: set[str]) -> int:
    changed = 0
    for path in paths:
        cur = conn.execute(
            "UPDATE library_items SET is_present_on_disk = 0 "
            "WHERE file_path = ? AND is_present_on_disk = 1",
            (path,),
        )
        changed += cur.rowcount
    return changed


def get_progress(conn: sqlite3.Connection, key: str) -> Progress | None:
    row = conn.execute(
        "SELECT max_season_seen, max_episode_seen, progress_state FROM show_progress "
        "WHERE media_key = ?",
        (key,),
    ).fetchone()
    return Progress(row[0], row[1], row[2]) if row else None


def _advance_show(conn: sqlite3.Connection, key: str, title: str, episodes: list[Episode]) -> bool:
    current = get_progress(conn, key)
    after = advance(current, episodes)
    if after is None or after == current:
        return False
    conn.execute(
        """INSERT INTO show_progress (media_key, title, max_season_seen, max_episode_seen,
               progress_state) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(media_key) DO UPDATE SET max_season_seen = excluded.max_season_seen,
               max_episode_seen = excluded.max_episode_seen,
               progress_state = excluded.progress_state,
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""",
        (key, title, after.season, after.episode, after.state),
    )
    return True
