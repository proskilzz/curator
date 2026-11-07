# Curator — project notes for agents

Plan: ~/Brain/wiki/projects/curator.md (not in repo). One slice per session (Vikunja project "Curator").
Repo is PUBLIC: never commit personal paths, Downloads file names, keys or indexer URLs. Tests use made-up names.

## Commands
- `./check` — ruff (complexity ≤ 6), ruff format, mypy --strict, import-linter, pytest (cov ≥ 90%). Must pass.
- `uv run curator [--folder X] [--db PATH]` — opens the Mac window (pywebview). Scan button → review list (all ticked) → Save. Defaults ~/Downloads, ~/Library/Application Support/Curator/curator.db
- Test the window headless-ish: a script with `webview.start(fn, w)` + `w.evaluate_js(...)` clicks buttons and reads the DOM (see tests via `curator.app.Api` for logic).

## Layout (import-linter enforces it)
app → scan | store → progress → model. The page calls Python via `window.pywebview.api` (no web server, no port).  scan is offline (no sqlite/socket/urllib/http); store is the only SQL.

## Invariants
- library_items.media_key is an offline key (`local:tv:<slug>`, `local:movie:<slug>-<year>`) and never changes; slice 4 maps it to TMDB in a separate table.
- show_progress only moves forward. Only files NEW to the DB move it; a file coming back after deletion does not.
- 4+ new episodes of one season in one scan = pack → progress at the pack's first episode, 'unverified_pack'.
- Scan saves nothing; only Save writes. Unticked files go to excluded_files (shown unticked next scan); a show with no files left loses its progress row.
- Scanner trusts an episode only with an explicit S01E02 / 1x02 in the name; a movie needs a year or a release tag.

## Pitfalls
- 2026-11-06: guessit reads `IMG_1234.MOV` as S12E34 and `ScreenRecording_…20-47-18` as 28 episodes → camera/screen names are rejected before guessit (PERSONAL regex in scan/parse.py).
- 2026-11-06: guessit drops subtitles: "Dune Part Two (2024)" → title "Dune". Enricher must search with the year.
- 2026-11-06: import-linter needs `include_external_packages = true` to forbid stdlib modules.
- 2026-11-06: `screencapture` from Terminal gives a black image (no Screen Recording permission); verify the window via evaluate_js instead.
