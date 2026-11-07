"""Open the Curator window: `uv run curator` (or `curator --folder X --db Y`)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from curator.app.api import Api
from curator.store import default_db_path


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - opens a real window
    import webview

    args = _parser().parse_args(argv)
    api = Api(Path(args.folder).expanduser().resolve(), Path(args.db).expanduser())
    if args.picks:
        return print_picks(api)
    page = files("curator.app").joinpath("page.html").read_text()
    webview.create_window("Curator", html=page, js_api=api, width=760, height=820)
    webview.start()
    return 0


def print_picks(api: Api) -> int:  # pragma: no cover - real network + local model
    result = api.picks()
    if result["error"]:
        print(result["error"])
    for p in result["picks"]:
        print(f"{p['slot']}: {p['title']} ({p['year']}, {p['kind']}, {p['rating']})")
        print(f"   {p['reason']}  [{p['reason_by']}]")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="curator")
    parser.add_argument("--folder", default="~/Downloads")
    parser.add_argument("--db", default=str(default_db_path()))
    parser.add_argument("--picks", action="store_true", help="print 3 picks, no window")
    return parser
