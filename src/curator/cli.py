"""Command line: `curator scan [FOLDER] [--db PATH]`."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from curator.model import Parsed, Skipped, SkipReason
from curator.scan import scan_folder
from curator.store import ScanCounts, connect, default_db_path, save_scan
from curator.store.db import get_progress


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a folder: {root}", file=sys.stderr)
        return 2
    return cmd_scan(root, Path(args.db).expanduser())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="curator")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="find movies and TV episodes in a folder")
    scan.add_argument("folder", nargs="?", default="~/Downloads")
    scan.add_argument("--db", default=str(default_db_path()))
    return parser


def cmd_scan(root: Path, db_path: Path) -> int:
    results = list(scan_folder(root))
    parsed = [r for r in results if isinstance(r, Parsed)]
    skipped = Counter(r.reason for r in results if isinstance(r, Skipped))
    conn = connect(db_path)
    counts = save_scan(conn, root, parsed)
    print(_report(root, parsed, skipped, counts, conn))
    conn.close()
    return 0


def _report(
    root: Path,
    parsed: list[Parsed],
    skipped: Counter[SkipReason],
    counts: ScanCounts,
    conn: sqlite3.Connection,
) -> str:
    movies = sorted({p.title for p in parsed if p.kind == "movie"})
    shows = sorted({(p.title, p.media_key) for p in parsed if p.kind == "episode"})
    lines = [
        f"Scanned {root}",
        f"  {len(movies)} movies, {len(parsed) - len(movies)} episode files in {len(shows)} shows",
        f"  {counts.new} new, {counts.seen_again} already known, {counts.missing} gone from disk",
    ]
    lines += [f"  skipped {n}: {reason}" for reason, n in skipped.most_common()]
    lines += [f"  movie: {m}" for m in movies]
    for title, key in shows:
        p = get_progress(conn, key)
        where = f"S{p.season:02d}E{p.episode:02d} ({p.state})" if p else "no progress yet"
        lines.append(f"  show:  {title}: {where}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
