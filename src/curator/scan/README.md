# scan
Owns: walking a folder and turning file names into movies / TV episodes (guessit + our rules).
Must not: touch the network or the database. Pure input → `Parsed | Skipped` (see `curator.model`).
Entry point: `scan_folder(root) -> Iterator[Parsed | Skipped]`.
