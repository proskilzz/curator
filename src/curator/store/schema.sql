-- From Argon review §5 (library_items, show_progress). Later slices add more tables.
CREATE TABLE IF NOT EXISTS library_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path           TEXT NOT NULL UNIQUE,
    file_name           TEXT NOT NULL,
    file_size_bytes     INTEGER NOT NULL,
    file_mtime          INTEGER NOT NULL,
    stream_kind         TEXT NOT NULL CHECK (stream_kind IN ('movie', 'episode', 'youtube')),
    media_key           TEXT NOT NULL, -- offline key 'local:tv:severance'; slice 4 maps to TMDB
    parsed_title        TEXT NOT NULL,
    parsed_year         INTEGER,
    season_number       INTEGER,
    episode_number      INTEGER,
    resolution          TEXT,
    video_codec         TEXT,
    is_present_on_disk  INTEGER NOT NULL DEFAULT 1 CHECK (is_present_on_disk IN (0, 1)),
    first_seen_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_library_media_key ON library_items(media_key);
CREATE INDEX IF NOT EXISTS idx_library_stream_kind ON library_items(stream_kind, is_present_on_disk);

CREATE TABLE IF NOT EXISTS show_progress (
    media_key           TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    max_season_seen     INTEGER NOT NULL DEFAULT 1,
    max_episode_seen    INTEGER NOT NULL DEFAULT 1,
    progress_state      TEXT NOT NULL DEFAULT 'tracking'
                        CHECK (progress_state IN ('tracking', 'unverified_pack', 'completed', 'dropped')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Files the user unticked in the review screen: kept out of the library and progress.
CREATE TABLE IF NOT EXISTS excluded_files (
    file_path           TEXT PRIMARY KEY,
    excluded_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Slice 4: what TMDB + TVmaze said about each library title, keyed by the offline media_key
-- (library_items.media_key never changes). tmdb_id NULL = looked up, not found.
CREATE TABLE IF NOT EXISTS enrichment_cache (
    media_key           TEXT PRIMARY KEY,
    kind                TEXT NOT NULL CHECK (kind IN ('movie', 'tv')),
    title               TEXT NOT NULL,
    tmdb_id             INTEGER,
    release_year        INTEGER,
    imdb_id             TEXT,
    tvdb_id             INTEGER,
    tvmaze_id           INTEGER,
    overview_sanitized  TEXT NOT NULL DEFAULT '',
    genres_json         TEXT NOT NULL DEFAULT '[]',
    poster_path         TEXT,
    show_status         TEXT,
    latest_season       INTEGER,
    latest_episode      INTEGER,
    latest_air_date     TEXT,
    next_season         INTEGER,
    next_episode        INTEGER,
    next_air_date       TEXT,
    fetched_at          TEXT NOT NULL,
    expires_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enrichment_tmdb ON enrichment_cache(tmdb_id, kind);
