"""When each folder was last saved, and which library files were on disk then."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from curator.store.db import under_root

_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def record_save(conn: sqlite3.Connection, root: Path, now: datetime) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO scan_history (folder, saved_at) VALUES (?, ?)",
            (str(root), now.astimezone(UTC).strftime(_FORMAT)),
        )


def last_saved(conn: sqlite3.Connection, root: Path) -> datetime | None:
    """From scan_history; libraries saved before that table existed fall back to the newest
    library_items.last_seen_at under root (Save stamps every file it keeps)."""
    sql = "SELECT saved_at FROM scan_history WHERE folder = ?"
    row = conn.execute(sql, (str(root),)).fetchone()
    if row:
        return _parse(row[0])
    prefix = str(root).rstrip(os.sep) + os.sep
    rows = conn.execute("SELECT file_path, last_seen_at FROM library_items")
    seen = [stamp for path, stamp in rows if path.startswith(prefix)]
    return _parse(max(seen)) if seen else None


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, _FORMAT).replace(tzinfo=UTC)


def present_paths(conn: sqlite3.Connection, root: Path) -> set[str]:
    """Library files under root that were on disk at the last save."""
    sql = "SELECT file_path FROM library_items WHERE is_present_on_disk = 1"
    return under_root(conn, sql, root)
