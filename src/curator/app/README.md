# app
Owns: the Mac window (pywebview) and the review screen: Scan button → found items, all ticked → Save.
Must not: parse file names or run SQL itself; it calls `curator.scan` and `curator.store`.
`Api` (api.py) is what the page calls via `window.pywebview.api.*`; it returns plain JSON dicts and is tested without a window.
