# store
Owns: the SQLite file (schema, library_items, show_progress, excluded_files). Only module that runs SQL.
Must not: parse file names or touch the network. Gets `Parsed` items, gives back counts.
Entry points: `connect(path)`, `save_scan(conn, root, items)`, `save_review(conn, root, items, keep)`.
