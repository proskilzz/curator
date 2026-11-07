# store
Owns: the SQLite file (schema, library_items, show_progress, excluded_files, enrichment_cache, scan_history). Only module that runs SQL.
Must not: parse file names or touch the network. Gets `Parsed` items, gives back counts.
Entry points: `connect(path)`, `save_scan(conn, root, items)`, `save_review(conn, root, items, keep)`,
`due_lookups(conn, now)` → `Lookup`s to fetch, `save_enrichment(conn, e, now)`, `enrichments(conn)`.
`record_save(conn, root, now)` / `last_saved(conn, root)`, `present_paths(conn, root)` (for "since last scan").
