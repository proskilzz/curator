"""Acceptance examples for the file-name rules. Names are made up; never use real Downloads."""

from __future__ import annotations

import pytest

from curator.model import Episode, FileInfo, Movie, Parsed, Skipped, SkipReason
from curator.scan import parse_file


def _parse(name: str) -> Parsed | Skipped:
    return parse_file(FileInfo(path=f"/x/{name}", name=name, size_bytes=1, mtime=0))


@pytest.mark.parametrize(
    ("name", "media"),
    [
        ("Severance.S02E03.1080p.WEB-DL.x265-GRP.mkv", Episode("Severance", 2, 3)),
        ("The.Office.US.S03E05.720p.mkv", Episode("The Office", 3, 5)),
        ("Severance.S01E01-E02.1080p.mkv", Episode("Severance", 1, 2)),
        ("Some Show 1x07 HDTV.avi", Episode("Some Show", 1, 7)),
        ("Dune Part Two (2024).mp4", Movie("Dune", 2024)),
        ("Some Film 2026 1080p WEB-DL HEVC x265 5.1 GRP.mkv", Movie("Some Film", 2026)),
        ("Old.Movie.720p.BluRay.x264.mkv", Movie("Old Movie", None)),
    ],
)
def test_recognises_media(name: str, media: Movie | Episode) -> None:
    result = _parse(name)
    assert isinstance(result, Parsed)
    assert result.media == media


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("IMG_1234.MOV", SkipReason.PERSONAL),  # guessit alone says S12E34
        ("DSCF0001.MOV", SkipReason.PERSONAL),
        ("video-1700000000_singular_display.MOV", SkipReason.PERSONAL),
        ("ScreenRecording_11-05-2026 20-47-18_1.MP4", SkipReason.PERSONAL),
        ("PXL_20261001_123456789.mp4", SkipReason.PERSONAL),
        ("YTDown.com_YouTube_Media_dQw4w9WgXcQ_Some-Video_002_720p.mp4", SkipReason.YOUTUBE),
        ("Some.Film.2026.1080p.sample.mkv", SkipReason.SAMPLE),
        ("holiday.mp4", SkipReason.NO_SIGNAL),
        ("party 3.mov", SkipReason.NO_SIGNAL),
    ],
)
def test_skips_non_media(name: str, reason: SkipReason) -> None:
    result = _parse(name)
    assert isinstance(result, Skipped)
    assert result.reason == reason


def test_media_keys_and_tags() -> None:
    ep = _parse("Severance.S02E03.1080p.WEB-DL.x265-GRP.mkv")
    film = _parse("Dune Part Two (2024).mp4")
    nodate = _parse("Old.Movie.720p.BluRay.x264.mkv")
    assert isinstance(ep, Parsed) and isinstance(film, Parsed) and isinstance(nodate, Parsed)
    assert ep.media_key == "local:tv:severance"
    assert (ep.kind, ep.title, ep.resolution, ep.video_codec) == (
        "episode",
        "Severance",
        "1080p",
        "H.265",
    )
    assert film.media_key == "local:movie:dune-2024"
    assert (film.kind, film.title) == ("movie", "Dune")
    assert nodate.media_key == "local:movie:old-movie"
