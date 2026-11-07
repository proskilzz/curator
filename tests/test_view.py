"""Sentences on the shows / movies cards."""

from __future__ import annotations

from datetime import date

from curator.app.view import behind, show_card, when_text
from curator.model import Enrichment, EpisodeRef, Progress

TODAY = date(2026, 11, 6)  # a Friday


def test_behind() -> None:
    at = Progress(2, 3, "tracking")
    assert behind(at, EpisodeRef(2, 3, None)) == ""
    assert behind(at, EpisodeRef(1, 9, None)) == ""
    assert behind(None, EpisodeRef(2, 9, None)) == ""
    assert behind(at, None) == ""
    assert behind(at, EpisodeRef(2, 4, None)) == "1 newer episode out, up to S02E04"
    assert behind(at, EpisodeRef(2, 6, None)) == "3 newer episodes out, up to S02E06"
    assert behind(at, EpisodeRef(3, 1, None)) == "A newer season is out, up to S03E01"


def test_when_text() -> None:
    assert when_text("2026-11-06", TODAY) == "today"
    assert when_text("2026-11-07", TODAY) == "tomorrow"
    assert when_text("2026-11-13", TODAY) == "on Fri 13 Nov (in 7 days)"
    assert when_text("2026-11-01", TODAY) == "on Sun 1 Nov"
    assert when_text(None, TODAY) == "(date not announced)"


def test_show_card_next_line() -> None:
    base = Enrichment("local:tv:x", "tv", "X", tmdb_id=1)
    assert show_card(base, None, TODAY)["next"] == "No next episode announced"
    ended = Enrichment("local:tv:x", "tv", "X", tmdb_id=1, show_status="Ended")
    assert show_card(ended, None, TODAY)["next"] == "Show has ended"
    missing = Enrichment("local:tv:x", "tv", "X")
    assert show_card(missing, None, TODAY) | {} == {
        "title": "X",
        "found": False,
        "at": "",
        "status": "",
        "behind": "",
        "next": "",
        "genres": "",
    }


def test_ago_text() -> None:
    from datetime import datetime, timedelta

    from curator.app.view import ago_text

    now = datetime(2026, 11, 6, 12, 0)
    assert ago_text(now - timedelta(seconds=20), now) == "just now"
    assert ago_text(now - timedelta(minutes=1), now) == "1 minute ago"
    assert ago_text(now - timedelta(hours=5, minutes=9), now) == "5 hours ago"
    assert ago_text(now - timedelta(days=1, hours=2), now) == "1 day ago"
    assert ago_text(now - timedelta(days=12), now) == "12 days ago"
