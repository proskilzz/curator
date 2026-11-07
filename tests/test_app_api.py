"""End to end through the app API (what the Scan / Save buttons call)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from curator.app import Api

FILES = [
    "Severance.S02E03.1080p.WEB-DL.mkv",
    "Some Film 2026 1080p WEB-DL x265.mkv",
    "Phone/IMG_1234.MOV",
    "installer.dmg",
    "bundle.zip",
    "setup.exe",
    ".hidden/Secret.S01E01.mkv",
    "Tool.app/Contents/Intro.S01E01.mp4",
]


def _make(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")


def _rows(db: Path, sql: str) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def _ids(found: dict[str, Any], *titles: str) -> list[int]:
    return [i["id"] for i in found["items"] if i["title"] in titles]


def _api(tmp_path: Path, names: list[str]) -> tuple[Api, Path, Path]:
    root, db = tmp_path / "dl", tmp_path / "db" / "curator.db"
    _make(root, names)
    return Api(root, db), root, db


def test_scan_shows_everything_ticked_and_saves_nothing(tmp_path: Path) -> None:
    api, root, db = _api(tmp_path, FILES)
    (root / "link.mkv").symlink_to(root / "Severance.S02E03.1080p.WEB-DL.mkv")
    found = api.scan()
    items = [
        (i["kind"], i["title"], i["detail"], i["status"], i["checked"]) for i in found["items"]
    ]
    assert items == [
        ("movie", "Some Film", "2026", "new", True),
        ("episode", "Severance", "Season 2, episode 3", "new", True),
    ]
    assert found["skipped"] == [{"reason": "camera or screen recording", "count": 1}]
    assert _rows(db, "SELECT COUNT(*) FROM library_items") == [(0,)]


def test_untick_keeps_item_out(tmp_path: Path) -> None:
    api, _, db = _api(tmp_path, FILES)
    found = api.scan()
    result = api.save(_ids(found, "Severance"))
    assert result["added"] == 1 and result["excluded"] == 1
    assert result["shows"] == [{"title": "Severance", "where": "S02E03", "state": "tracking"}]
    assert _rows(db, "SELECT media_key FROM library_items") == [("local:tv:severance",)]

    again = api.scan()
    assert [(i["title"], i["status"], i["checked"]) for i in again["items"]] == [
        ("Some Film", "left out before", False),
        ("Severance", "in library", True),
    ]


def test_untick_whole_show_removes_progress_and_retick_restores(tmp_path: Path) -> None:
    api, _, db = _api(tmp_path, FILES)
    api.save(_ids(api.scan(), "Severance", "Some Film"))
    assert _rows(db, "SELECT COUNT(*) FROM show_progress") == [(1,)]

    result = api.save(_ids(api.scan(), "Some Film"))
    assert result["excluded"] == 1 and result["kept"] == 1
    assert _rows(db, "SELECT COUNT(*) FROM show_progress") == [(0,)]

    api.save(_ids(api.scan(), "Severance", "Some Film"))
    assert _rows(db, "SELECT max_season_seen, max_episode_seen FROM show_progress") == [(2, 3)]
    assert _rows(db, "SELECT COUNT(*) FROM excluded_files") == [(0,)]


def test_deleted_file_keeps_progress(tmp_path: Path) -> None:
    api, root, db = _api(tmp_path, ["Severance.S02E03.mkv", "Severance.S01E01.mkv"])
    api.save(_ids(api.scan(), "Severance"))
    (root / "Severance.S02E03.mkv").unlink()
    result = api.save(_ids(api.scan(), "Severance"))
    assert (result["added"], result["kept"], result["gone"]) == (0, 1, 1)
    assert _rows(db, "SELECT max_season_seen, max_episode_seen FROM show_progress") == [(2, 3)]


def test_season_pack(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path, [f"Andor.S01E{n:02d}.720p.mkv" for n in range(1, 7)])
    result = api.save(_ids(api.scan(), "Andor"))
    assert result["shows"] == [{"title": "Andor", "where": "S01E01", "state": "unverified_pack"}]


def test_bad_ids_ignored(tmp_path: Path) -> None:
    api, _, db = _api(tmp_path, FILES)
    api.scan()
    assert api.save([99, -1])["excluded"] == 2
    assert _rows(db, "SELECT COUNT(*) FROM library_items") == [(0,)]


# --- Check new episodes (slice 4) ---

from dataclasses import replace  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

from curator.enrich import EnrichError, KeyMissing  # noqa: E402
from curator.model import Enrichment, EpisodeRef, Lookup  # noqa: E402

LOOKUPS = [
    "Night.Office.S02E03.1080p.WEB-DL.mkv",
    "Night.Office.S02E04.1080p.WEB-DL.mkv",
    "Some Film 2026 1080p WEB-DL x265.mkv",
    "Unknown Thing 1999 1080p BluRay.mkv",
]


class FakeEnricher:
    def __init__(self, fail_after: int | None = None) -> None:
        self.asked: list[Lookup] = []
        self.fail_after = fail_after

    def __call__(self, lookup: Lookup) -> Enrichment:
        if self.fail_after is not None and len(self.asked) >= self.fail_after:
            raise EnrichError("network error")
        self.asked.append(lookup)
        if lookup.title.startswith("Unknown"):
            return Enrichment(lookup.media_key, lookup.kind, lookup.title, year=lookup.year)
        base = Enrichment(lookup.media_key, lookup.kind, lookup.title, tmdb_id=1, year=2026)
        if lookup.kind == "movie":
            return replace(base, genres=("Thriller",), overview="A film.")
        return replace(
            base,
            show_status="Running",
            latest=EpisodeRef(2, 8, "2026-11-06"),
            upcoming=EpisodeRef(2, 9, "2026-11-13"),
        )


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _saved(tmp_path: Path, fake: FakeEnricher, clock: Clock) -> Api:
    root, db = tmp_path / "dl", tmp_path / "db" / "curator.db"
    _make(root, LOOKUPS)
    api = Api(root, db, enricher=lambda: fake, clock=clock)
    found = api.scan()
    api.save([i["id"] for i in found["items"]])
    return api


def test_refresh_lists_shows_with_next_episode_and_movies(tmp_path: Path) -> None:
    fake, clock = FakeEnricher(), Clock()
    r = _saved(tmp_path, fake, clock).refresh()
    assert (r["error"], r["looked_up"]) == ("", 3)
    assert [(lk.kind, lk.title, lk.year) for lk in fake.asked] == [
        ("movie", "Some Film", 2026),
        ("movie", "Unknown Thing", 1999),
        ("tv", "Night Office", None),
    ]
    [show] = r["shows"]
    assert show["at"] == "S02E04"
    assert show["behind"] == "4 newer episodes out, up to S02E08"
    assert show["next"] == "Next: S02E09 on Fri 13 Nov (in 7 days)"
    assert [(m["title"], m["found"], m["genres"]) for m in r["movies"]] == [
        ("Some Film", True, "Thriller"),
        ("Unknown Thing", False, ""),
    ]


def test_refresh_uses_the_cache_until_it_is_stale(tmp_path: Path) -> None:
    fake, clock = FakeEnricher(), Clock()
    api = _saved(tmp_path, fake, clock)
    api.refresh()
    assert api.refresh()["looked_up"] == 0
    clock.now += timedelta(hours=13)  # shows are stale, movies are not
    assert api.refresh()["looked_up"] == 1
    clock.now += timedelta(days=3)  # 'not found' gets retried after 3 days
    assert [lk.title for lk in fake.asked[-2:]] == ["Night Office", "Night Office"]
    api.refresh()
    assert "Unknown Thing" in [lk.title for lk in fake.asked[-2:]]


def test_refresh_without_a_key_or_network(tmp_path: Path) -> None:
    def no_key() -> FakeEnricher:
        raise KeyMissing("none")

    clock = Clock()
    api = _saved(tmp_path, FakeEnricher(), clock)
    api._enricher = no_key
    r = api.refresh()
    assert r["error"].startswith("No TMDB key") and r["shows"] == [] and r["looked_up"] == 0
    api._enricher = lambda: FakeEnricher(fail_after=1)
    r = api.refresh()
    assert r["error"].startswith("Couldn't reach") and r["looked_up"] == 1
    assert len(r["movies"]) == 1


# --- Reopen the app days later and rescan ---


def test_reopen_shows_last_scan_and_rescan_reports_what_changed(tmp_path: Path) -> None:
    fake, clock = FakeEnricher(), Clock()
    first = _saved(tmp_path, fake, clock)
    first.refresh()
    root, db = first.root, first.db_path

    clock.now += timedelta(days=3)  # the app was closed and forgotten
    again = Api(root, db, enricher=lambda: fake, clock=clock)
    opened = again.opened()
    assert opened["last_scan"] == "3 days ago"
    assert [s["title"] for s in opened["shows"]] == ["Night Office"]
    assert len(fake.asked) == 3  # opening the window made no lookups

    (root / "Night.Office.S02E03.1080p.WEB-DL.mkv").unlink()
    _make(root, ["Night.Office.S02E05.1080p.WEB-DL.mkv"])
    found = again.scan()
    assert found["changes"] == {"since": "3 days ago", "new": 1, "known": 3, "gone": 1}
    assert [i["status"] for i in found["items"] if i["detail"].endswith("episode 5")] == ["new"]
    again.save([i["id"] for i in found["items"]])
    assert again.opened()["last_scan"] == "just now"


def test_first_open_has_no_last_scan(tmp_path: Path) -> None:
    api, _, _ = _api(tmp_path, [])
    assert api.opened() == {"folder": str(api.root), "last_scan": "", "shows": [], "movies": []}
    assert api.scan()["changes"] == {"since": "", "new": 0, "known": 0, "gone": 0}


def test_library_saved_before_scan_history_still_shows_last_scan(tmp_path: Path) -> None:
    clock = Clock()
    api = _saved(tmp_path, FakeEnricher(), clock)
    with sqlite3.connect(api.db_path) as conn:
        conn.execute("DELETE FROM scan_history")
        conn.execute("UPDATE library_items SET last_seen_at = '2026-11-04T12:00:00Z'")
    assert api.opened()["last_scan"] == "2 days ago"
