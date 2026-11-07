"""End to end: a fake Downloads folder → curator scan → SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from curator.cli import main

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


def _rows(db: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def test_scan_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, db = tmp_path / "dl", tmp_path / "db" / "curator.db"
    _make(root, FILES)
    (root / "link.mkv").symlink_to(root / "Severance.S02E03.1080p.WEB-DL.mkv")

    assert main(["scan", str(root), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "1 movies, 1 episode files in 1 shows" in out
    assert "skipped 1: camera or screen recording" in out
    assert "show:  Severance: S02E03 (tracking)" in out
    kinds = _rows(db, "SELECT stream_kind, media_key FROM library_items ORDER BY stream_kind")
    assert kinds == [("episode", "local:tv:severance"), ("movie", "local:movie:some-film-2026")]


def test_rescan_marks_missing_and_keeps_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, db = tmp_path / "dl", tmp_path / "curator.db"
    _make(root, ["Severance.S02E03.mkv", "Severance.S01E01.mkv"])
    main(["scan", str(root), "--db", str(db)])
    (root / "Severance.S02E03.mkv").unlink()

    main(["scan", str(root), "--db", str(db)])
    out = capsys.readouterr().out
    assert "0 new, 1 already known, 1 gone from disk" in out
    assert _rows(db, "SELECT max_season_seen, max_episode_seen FROM show_progress") == [(2, 3)]
    present = _rows(db, "SELECT file_name, is_present_on_disk FROM library_items ORDER BY 1")
    assert present == [("Severance.S01E01.mkv", 1), ("Severance.S02E03.mkv", 0)]


def test_season_pack(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, db = tmp_path / "dl", tmp_path / "curator.db"
    _make(root, [f"Andor.S01E{n:02d}.720p.mkv" for n in range(1, 7)])
    main(["scan", str(root), "--db", str(db)])
    assert "show:  Andor: S01E01 (unverified_pack)" in capsys.readouterr().out


def test_bad_folder(tmp_path: Path) -> None:
    assert main(["scan", str(tmp_path / "nope"), "--db", str(tmp_path / "c.db")]) == 2
