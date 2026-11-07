# Curator — project notes for agents

Plan: ~/Brain/wiki/projects/curator.md (not in repo). One slice per session (Vikunja project "Curator").
Repo is PUBLIC: never commit personal paths, Downloads file names, keys or indexer URLs. Tests use made-up names.

## Commands
- `./check` — ruff (complexity ≤ 6), ruff format, mypy --strict, import-linter, pytest (cov ≥ 90%). Must pass.
- `uv run curator scan [FOLDER] [--db PATH]` — default ~/Downloads → ~/Library/Application Support/Curator/curator.db

## Layout (import-linter enforces it)
cli → scan | store → progress → model.  scan is offline (no sqlite/socket/urllib/http); store is the only SQL.

## Invariants
- library_items.media_key is an offline key (`local:tv:<slug>`, `local:movie:<slug>-<year>`) and never changes; slice 4 maps it to TMDB in a separate table.
- show_progress only moves forward. Only files NEW to the DB move it; a file coming back after deletion does not.
- 4+ new episodes of one season in one scan = pack → progress at the pack's first episode, 'unverified_pack'.
- Scanner trusts an episode only with an explicit S01E02 / 1x02 in the name; a movie needs a year or a release tag.

## Pitfalls
- 2026-11-06: guessit reads `IMG_1234.MOV` as S12E34 and `ScreenRecording_…20-47-18` as 28 episodes → camera/screen names are rejected before guessit (PERSONAL regex in scan/parse.py).
- 2026-11-06: guessit drops subtitles: "Dune Part Two (2024)" → title "Dune". Enricher must search with the year.
- 2026-11-06: import-linter needs `include_external_packages = true` to forbid stdlib modules.
