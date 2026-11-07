"""One call per library title: Lookup -> Enrichment."""

from __future__ import annotations

from curator.enrich.details import title_info
from curator.enrich.net import Fetch, http_fetch, tmdb_key
from curator.enrich.tmdb import Tmdb, match_movie, match_show
from curator.enrich.tvmaze import add_episodes
from curator.model import Enrichment, Lookup, TitleInfo


class Enricher:
    def __init__(self, fetch: Fetch, key: str) -> None:
        self._fetch = fetch
        self._tmdb = Tmdb(fetch, key)

    def __call__(self, lookup: Lookup) -> Enrichment:
        if lookup.kind == "movie":
            return match_movie(self._tmdb, lookup)
        show = match_show(self._tmdb, lookup)
        return add_episodes(self._fetch, show) if show.found else show

    def title(self, kind: str, tmdb_id: int) -> TitleInfo | None:
        """Details + keywords + creators + recommendations (for picks)."""
        return title_info(self._tmdb, kind, tmdb_id)


def default_enricher() -> Enricher:
    """Real network + key from the Keychain. Raises KeyMissing if there is no key."""
    return Enricher(http_fetch, tmdb_key())
