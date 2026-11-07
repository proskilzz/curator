"""What the page can call. Plain JSON in and out; one SQLite connection per call
(pywebview runs calls on its own threads)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from curator.model import Episode, Parsed, Skipped
from curator.scan import scan_folder
from curator.store import connect, excluded_paths, get_progress, library_paths, save_review


class Api:
    def __init__(self, root: Path, db_path: Path) -> None:
        self.root = root
        self.db_path = db_path
        self._found: list[Parsed] = []

    def scan(self) -> dict[str, Any]:
        """Scan the folder (saves nothing). Every item comes back ticked except files the
        user unticked before."""
        results = list(scan_folder(self.root))
        self._found = sorted((r for r in results if isinstance(r, Parsed)), key=_sort_key)
        skipped = Counter(r.reason.value for r in results if isinstance(r, Skipped))
        conn = connect(self.db_path)
        known, excluded = library_paths(conn, self.root), excluded_paths(conn, self.root)
        conn.close()
        return {
            "folder": str(self.root),
            "skipped": [{"reason": r, "count": n} for r, n in skipped.most_common()],
            "items": [_item(i, p, known, excluded) for i, p in enumerate(self._found)],
        }

    def save(self, keep_ids: list[int]) -> dict[str, Any]:
        """Ticked ids go into the library; the rest are excluded."""
        keep = {self._found[i].file.path for i in keep_ids if 0 <= i < len(self._found)}
        conn = connect(self.db_path)
        counts, excluded = save_review(conn, self.root, self._found, keep)
        shows = sorted({(p.title, p.media_key) for p in self._found if p.file.path in keep})
        progress = [(t, get_progress(conn, k)) for t, k in shows]
        conn.close()
        return {
            "added": counts.new,
            "kept": counts.seen_again,
            "excluded": excluded,
            "gone": counts.missing,
            "shows": [
                {"title": t, "where": f"S{p.season:02d}E{p.episode:02d}", "state": p.state}
                for t, p in progress
                if p
            ],
        }


def _sort_key(p: Parsed) -> tuple[int, str, int, int]:
    if isinstance(p.media, Episode):
        return (1, p.title.lower(), p.media.season, p.media.episode)
    return (0, p.title.lower(), 0, 0)


def _item(i: int, p: Parsed, known: set[str], excluded: set[str]) -> dict[str, Any]:
    media = p.media
    if isinstance(media, Episode):
        detail = f"Season {media.season}, episode {media.episode}"
    else:
        detail = str(media.year) if media.year else "year unknown"
    status = "in library" if p.file.path in known else "new"
    if p.file.path in excluded:
        status = "left out before"
    return {
        "id": i,
        "kind": p.kind,
        "title": p.title,
        "detail": detail,
        "quality": p.resolution or "",
        "file": p.file.name,
        "status": status,
        "checked": p.file.path not in excluded,
    }
