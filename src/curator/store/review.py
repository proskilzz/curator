"""Save the user's choices from the review screen (ticked = in the library)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from curator.model import Parsed
from curator.store.db import ScanCounts, save_scan, under_root


def library_paths(conn: sqlite3.Connection, root: Path) -> set[str]:
    return under_root(conn, "SELECT file_path FROM library_items", root)


def excluded_paths(conn: sqlite3.Connection, root: Path) -> set[str]:
    return under_root(conn, "SELECT file_path FROM excluded_files", root)


def save_review(
    conn: sqlite3.Connection, root: Path, items: Iterable[Parsed], keep: set[str]
) -> tuple[ScanCounts, int]:
    """Ticked files go through save_scan; unticked ones are excluded and removed from the
    library. A show left with no files loses its progress row. Returns (counts, excluded)."""
    items = list(items)
    dropped = [i.file.path for i in items if i.file.path not in keep]
    with conn:
        conn.executemany("DELETE FROM library_items WHERE file_path = ?", [(p,) for p in dropped])
        conn.executemany(
            "INSERT OR IGNORE INTO excluded_files (file_path) VALUES (?)", [(p,) for p in dropped]
        )
        conn.executemany("DELETE FROM excluded_files WHERE file_path = ?", [(p,) for p in keep])
        conn.execute(
            "DELETE FROM show_progress WHERE media_key NOT IN (SELECT media_key FROM library_items)"
        )
    counts = save_scan(conn, root, [i for i in items if i.file.path in keep])
    return counts, len(dropped)
