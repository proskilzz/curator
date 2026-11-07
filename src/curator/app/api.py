"""What the page can call. Plain JSON in and out; one SQLite connection per call
(pywebview runs calls on its own threads)."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from curator.app.picking import ModelFactory, TitleSource, make_picks
from curator.app.view import ago_text, movie_card, show_card
from curator.enrich import EnrichError, KeyMissing, default_enricher
from curator.llm import LocalModel, default_model_path
from curator.model import Enrichment, Episode, Lookup, Parsed, Skipped
from curator.scan import scan_folder
from curator.store import (
    connect,
    due_lookups,
    enrichments,
    excluded_paths,
    get_progress,
    last_saved,
    library_paths,
    present_paths,
    record_save,
    save_enrichment,
    save_review,
)

EnricherFactory = Callable[[], Callable[[Lookup], Enrichment]]

NO_KEY = "No TMDB key yet, so shows and movies can't be looked up."
OFFLINE = "Couldn't reach TMDB or TVmaze. Showing what was found before."


class Api:
    def __init__(
        self,
        root: Path,
        db_path: Path,
        enricher: EnricherFactory = default_enricher,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        titles: Callable[[], TitleSource] | None = None,
        model: ModelFactory = lambda: LocalModel(default_model_path()),
    ) -> None:
        self.root = root
        self.db_path = db_path
        self._found: list[Parsed] = []
        self._enricher = enricher
        self._clock = clock
        self._titles = titles or (lambda: default_enricher().title)
        self._model = model

    def scan(self) -> dict[str, Any]:
        """Scan the folder (saves nothing). Every item comes back ticked except files the
        user unticked before."""
        results = list(scan_folder(self.root))
        self._found = sorted((r for r in results if isinstance(r, Parsed)), key=_sort_key)
        skipped = Counter(r.reason.value for r in results if isinstance(r, Skipped))
        conn = connect(self.db_path)
        known, excluded = library_paths(conn, self.root), excluded_paths(conn, self.root)
        items = [_item(i, p, known, excluded) for i, p in enumerate(self._found)]
        changes = self._changes(conn, items, known)
        conn.close()
        return {
            "folder": str(self.root),
            "skipped": [{"reason": r, "count": n} for r, n in skipped.most_common()],
            "items": items,
            "changes": changes,
        }

    def opened(self) -> dict[str, Any]:
        """What the window shows when it opens: when this folder was last saved and the
        library as it was looked up last time. No scan, no network."""
        conn = connect(self.db_path)
        try:
            when = last_saved(conn, self.root)
            library = self._library(conn)
        finally:
            conn.close()
        last_scan = ago_text(when, self._clock()) if when else ""
        return {"folder": str(self.root), "last_scan": last_scan, **library}

    def _changes(
        self, conn: sqlite3.Connection, items: list[dict[str, Any]], known: set[str]
    ) -> dict[str, Any]:
        """A rescan compared with the last save: new files, files still there, files gone."""
        when = last_saved(conn, self.root)
        found = {p.file.path for p in self._found}
        return {
            "since": ago_text(when, self._clock()) if when else "",
            "new": sum(1 for i in items if i["status"] == "new"),
            "known": len(found & known),
            "gone": len(present_paths(conn, self.root) - found),
        }

    def save(self, keep_ids: list[int]) -> dict[str, Any]:
        """Ticked ids go into the library; the rest are excluded."""
        keep = {self._found[i].file.path for i in keep_ids if 0 <= i < len(self._found)}
        conn = connect(self.db_path)
        counts, excluded = save_review(conn, self.root, self._found, keep)
        record_save(conn, self.root, self._clock())
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

    def refresh(self) -> dict[str, Any]:
        """Look up library titles not checked recently, then list shows and movies."""
        conn = connect(self.db_path)
        try:
            looked_up, error = self._look_up_due(conn)
            library = self._library(conn)
        finally:
            conn.close()
        return {"error": error, "looked_up": looked_up, **library}

    def picks(self) -> dict[str, Any]:
        """3 picks from titles like the library (TMDB + plain-code score + local model)."""
        conn = connect(self.db_path)
        try:
            return make_picks(conn, self._titles, self._model, self._clock())
        except KeyMissing:
            return {"error": NO_KEY, "picks": []}
        except EnrichError:
            return {"error": OFFLINE, "picks": []}
        finally:
            conn.close()

    def _library(self, conn: sqlite3.Connection) -> dict[str, Any]:
        today = self._clock().astimezone().date()
        known = enrichments(conn)
        shows = [
            show_card(e, get_progress(conn, e.media_key), today) for e in known if e.kind == "tv"
        ]
        return {"shows": shows, "movies": [movie_card(e) for e in known if e.kind == "movie"]}

    def _look_up_due(self, conn: sqlite3.Connection) -> tuple[int, str]:
        due = due_lookups(conn, self._clock())
        if not due:
            return 0, ""
        done = 0
        try:
            enrich = self._enricher()
            for lookup in due:
                save_enrichment(conn, enrich(lookup), self._clock())
                done += 1
        except KeyMissing:
            return 0, NO_KEY
        except EnrichError:
            return done, OFFLINE
        return done, ""


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
