# enrich
Owns: talking to TMDB (match title → tmdb/imdb/tvdb ids, genres, overview) and TVmaze (latest + next episode). The TMDB key comes from the Keychain (`curator-tmdb`) and is never logged.
Must not: run SQL, read files or parse file names. `Lookup` in → `Enrichment` out (see `curator.model`); a 404 means "not found", any other failure raises `EnrichError`.
Entry points: `Enricher(fetch, key)(lookup)`, `default_enricher()` (real network + Keychain).
