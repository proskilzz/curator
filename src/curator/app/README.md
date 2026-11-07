# app
Owns: the Mac window (pywebview): Scan button → found items, all ticked → Save; "Check new episodes" → `Api.refresh()` (enrich due titles, list shows with next episode + movies).
`Api.picks()` (picking.py): seeds → cached TMDB titles → `curator.picks` score → `curator.llm` → check → `save_batch`; `curator --picks` prints them.
Must not: parse file names or run SQL itself; it calls `curator.scan`, `curator.store` and `curator.enrich`. `view.py` turns results into sentences.
`Api` (api.py) is what the page calls via `window.pywebview.api.*`; it returns plain JSON dicts and is tested without a window.
