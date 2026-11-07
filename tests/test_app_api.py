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
