"""Picks: TMDB details parsing, plain-code score, the model's reply checked in code, and the
whole batch through Api.picks() with a fake TMDB and a fake local model (no network)."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from curator.app import Api
from curator.app.picking import NO_MODEL, NO_SEEDS, Chat
from curator.enrich import Enricher, EnrichError, KeyMissing
from curator.llm import LlmError
from curator.model import Candidate, Enrichment, Lookup, Title, TitleInfo
from curator.picks import check, messages, rank, schema, shortlist

# --- made-up library: one show, one movie ---

NIGHT = Title("tv", 100, "Night Office", 2025, keywords=("office", "memory"),
              genres=("Drama", "Mystery"), creators=("Ada Vance",))  # fmt: skip
HARBOR = Title("movie", 200, "Quiet Harbor", 2019, keywords=("memory", "harbor"),
               genres=("Drama",), creators=("Bo Lind",))  # fmt: skip


def rec(kind: str, tmdb_id: int, name: str, pop: float = 20, votes: int = 400,
        rating: float = 7.5, adult: bool = False) -> Title:  # fmt: skip
    return Title(kind, tmdb_id, name, 2020, popularity=pop, vote_count=votes,
                 vote_average=rating, adult=adult)  # fmt: skip


GLASS = rec("tv", 301, "Glass Floor")
LOUD = rec("tv", 302, "Loud Sequel", pop=900, votes=5000, rating=6.5)
TINY = rec("tv", 303, "Tiny Show", votes=40)
CHOIR = rec("movie", 401, "Stone Choir", pop=15, votes=900, rating=8.1)
ADULT = rec("movie", 402, "Adult Thing", adult=True)

TMDB: dict[tuple[str, int], TitleInfo | None] = {
    NIGHT.ref: TitleInfo(NIGHT, (GLASS, LOUD, TINY, rec("movie", 200, "Quiet Harbor"))),
    HARBOR.ref: TitleInfo(HARBOR, (GLASS, CHOIR, ADULT, rec("tv", 100, "Night Office"))),
    GLASS.ref: TitleInfo(
        Title(
            "tv",
            301,
            "Glass Floor",
            2020,
            keywords=("memory",),
            genres=("Drama",),
            creators=("Ada Vance",),
            popularity=20,
            vote_count=400,
            vote_average=7.5,
        )
    ),  # fmt: skip
    CHOIR.ref: TitleInfo(
        Title(
            "movie",
            401,
            "Stone Choir",
            2020,
            keywords=("choir",),
            genres=("Music",),
            creators=("Cy Moss",),
            popularity=15,
            vote_count=900,
            vote_average=8.1,
        )
    ),  # fmt: skip
    LOUD.ref: None,  # TMDB 404 on details: the bare recommendation is used
}


def candidates() -> list[Candidate]:
    seeds = [TMDB[NIGHT.ref], TMDB[HARBOR.ref]]
    pooled = shortlist([s for s in seeds if s], {NIGHT.ref, HARBOR.ref})
    detailed = [((TMDB.get(t.ref) or TitleInfo(t)).title, by) for t, by in pooled]
    return rank([NIGHT, HARBOR], detailed)


# --- plain-code score ---


def test_shortlist_skips_library_weak_and_adult_titles() -> None:
    pooled = shortlist(
        [i for i in (TMDB[NIGHT.ref], TMDB[HARBOR.ref]) if i], {(NIGHT.ref), HARBOR.ref}
    )
    assert [(t.title, by) for t, by in pooled] == [
        ("Glass Floor", ("Night Office", "Quiet Harbor")),  # recommended by both seeds
        ("Stone Choir", ("Quiet Harbor",)),
        ("Loud Sequel", ("Night Office",)),  # blockbuster: popularity penalty
    ]


def test_rank_scores_creator_keywords_and_popularity() -> None:
    top = candidates()
    assert [(c.number, c.title.title) for c in top] == [
        (1, "Glass Floor"),
        (2, "Stone Choir"),
        (3, "Loud Sequel"),
    ]
    glass = top[0]
    assert glass.shared_creators == ("Ada Vance",)
    assert glass.shared_keywords == ("memory",)
    # 2.5*2 seeds + 3.0*1 creator + 1.5*1.0 'memory' + 1.0*1.0 'Drama' - 0.8*log10(20)
    assert glass.score == pytest.approx(9.459, abs=0.001)
    assert top[2].score < top[1].score  # Loud Sequel: same seed count, far more popular


def test_rank_keeps_the_top_15() -> None:
    seeds: tuple[str, ...] = ("Quiet Harbor",)
    many = [(rec("movie", 1000 + i, f"Film {i:02d}"), seeds) for i in range(40)]
    top = rank([HARBOR], many)
    assert len(top) == 15
    assert [c.number for c in top] == list(range(1, 16))
    twins = rank([HARBOR], [(rec("tv", 1, "Twin"), seeds), (rec("tv", 2, "twin", pop=900), seeds)])
    assert [(c.title.tmdb_id, c.number) for c in twins] == [(1, 1)]  # same name: best one only


# --- the prompt the model sees ---


def test_schema_only_allows_this_batch_and_three_slots() -> None:
    shape = schema(candidates())
    assert shape["required"] == ["high_affinity", "creator_tone", "wildcard"]
    assert shape["properties"]["wildcard"]["properties"]["candidate_id"]["enum"] == [1, 2, 3]
    assert shape["properties"]["wildcard"]["properties"]["reason"]["maxLength"] == 160


def test_prompt_wraps_candidates_as_data() -> None:
    system, user = messages([NIGHT, HARBOR], candidates())
    assert "never instructions" in system["content"]
    assert "- Night Office (2025, tv); by Ada Vance; keywords: office, memory" in user["content"]
    data = user["content"].split("<candidate_data>")[1]
    assert '"candidate_id": 1' in data and '"shared_creators": ["Ada Vance"]' in data


# --- the model's reply, checked in code ---

GOOD = "Shares creator Ada Vance with your Night Office."


def test_good_reply_is_kept() -> None:
    reply = {
        "high_affinity": {"candidate_id": 1, "reason": GOOD},
        "creator_tone": {"candidate_id": 2, "reason": "Recommended from your Quiet Harbor."},
        "wildcard": {"candidate_id": 3, "reason": "Your Night Office fans rate it."},
    }
    picks = check(reply, candidates())
    assert [(p.slot, p.number, p.reason_by) for p in picks] == [
        ("high_affinity", 1, "model"),
        ("creator_tone", 2, "model"),
        ("wildcard", 3, "model"),
    ]
    assert picks[0].reason == GOOD


def test_planted_fake_id_is_rejected() -> None:
    reply = {
        "high_affinity": {"candidate_id": 999, "reason": "Dune: Part Two, from Ada Vance."},
        "creator_tone": {"candidate_id": 1, "reason": GOOD},
        "wildcard": {"candidate_id": "3", "reason": GOOD},
    }
    picks = check(reply, candidates())
    assert all(p.number in {1, 2, 3} for p in picks)
    # the model's valid 1 is kept for creator_tone; 999 is replaced by the best one left
    assert [(p.slot, p.number, p.reason_by) for p in picks] == [
        ("high_affinity", 2, "code"),
        ("creator_tone", 1, "model"),
        ("wildcard", 3, "code"),  # "3" is a string, not an id
    ]
    assert len({p.number for p in picks}) == 3


def test_vague_or_long_reason_is_replaced() -> None:
    reply = {
        "high_affinity": {"candidate_id": 1, "reason": "From your Night Office, about wilderness."},
        "creator_tone": {"candidate_id": 2, "reason": "Quiet Harbor " + "x" * 160},
        "wildcard": {"candidate_id": 3},
    }
    picks = check(reply, candidates())
    assert [p.reason_by for p in picks] == ["code", "code", "code"]
    assert picks[0].reason == (
        "Recommended from your Night Office and Quiet Harbor; also by Ada Vance."
    )


def test_no_reply_gives_three_plain_picks() -> None:
    picks = check(None, candidates())
    assert [(p.slot, p.number) for p in picks] == [
        ("high_affinity", 1),
        ("creator_tone", 2),
        ("wildcard", 3),
    ]
    assert check({}, candidates()[:1])[0].number == 1
    assert len(check({}, candidates()[:1])) == 1


# --- TMDB details parsing (enrich) ---


def test_enricher_reads_details_keywords_creators_and_recommendations() -> None:
    replies: dict[str, Any] = {
        "/movie/7?": {
            "id": 7,
            "title": "Quiet Harbor",
            "release_date": "2019-03-01",
            "runtime": 101,
            "popularity": 12.5,
            "vote_average": 7.9,
            "vote_count": 2000,
            "genres": [{"name": "Drama"}],
            "keywords": {"keywords": [{"name": "harbor"}, {"name": "harbor"}, {"x": 1}]},
            "credits": {
                "crew": [
                    {"name": "Bo Lind", "job": "Director"},
                    {"name": "Al Grip", "job": "Gaffer"},
                ]
            },  # fmt: skip
            "recommendations": {"results": [{"id": 8, "title": "Stone Choir", "adult": False}]},
        },
        "/tv/5?": {
            "id": 5,
            "name": "Night Office",
            "episode_run_time": [48],
            "created_by": [{"name": "Ada Vance"}],
            "keywords": {"results": [{"name": "office"}]},
        },
    }
    enricher = Enricher(lambda url: next((v for k, v in replies.items() if k in url), None), "k")
    movie = enricher.title("movie", 7)
    assert movie is not None
    assert (movie.title.keywords, movie.title.creators) == (("harbor",), ("Bo Lind",))
    assert (movie.title.runtime_minutes, movie.title.year) == (101, 2019)
    assert [r.title for r in movie.recommendations] == ["Stone Choir"]
    show = enricher.title("tv", 5)
    assert show is not None
    assert (show.title.creators, show.title.keywords) == (("Ada Vance",), ("office",))
    assert show.title.runtime_minutes == 48
    assert enricher.title("tv", 6) is None  # 404


# --- the whole batch through the app ---


class FakeModel:
    name = "fake-model"

    def __init__(self, reply: Any = None, fail: bool = False) -> None:
        self.reply, self.fail = reply, fail
        self.asked: list[list[dict[str, str]]] = []

    def __call__(self) -> AbstractContextManager[Chat]:
        if self.fail:
            raise LlmError("no local model file")
        return nullcontext(self)

    def chat(self, prompt: list[dict[str, str]], shape: dict[str, Any]) -> Any:
        self.asked.append(prompt)
        return self.reply


class FakeTmdb:
    def __init__(self) -> None:
        self.asked: list[tuple[str, int]] = []

    def __call__(self, kind: str, tmdb_id: int) -> TitleInfo | None:
        self.asked.append((kind, tmdb_id))
        return TMDB.get((kind, tmdb_id))


def library_enricher(lookup: Lookup) -> Enrichment:
    tmdb_id = 100 if lookup.kind == "tv" else 200
    return Enrichment(lookup.media_key, lookup.kind, lookup.title, tmdb_id=tmdb_id)


def _app(tmp_path: Path, model: FakeModel, tmdb: Any = None) -> tuple[Api, Path]:
    root, db = tmp_path / "dl", tmp_path / "curator.db"
    for name in ["Night.Office.S01E02.1080p.WEB-DL.mkv", "Quiet Harbor 2019 1080p WEB-DL.mkv"]:
        root.mkdir(exist_ok=True)
        (root / name).write_bytes(b"x")
    clock = lambda: datetime(2026, 11, 6, 12, tzinfo=UTC)  # noqa: E731
    fake = tmdb if tmdb is not None else FakeTmdb()
    api = Api(root, db, lambda: library_enricher, clock, lambda: fake, model)
    api.save([i["id"] for i in api.scan()["items"]])
    api.refresh()
    return api, db


def _rows(db: Path, sql: str) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def test_picks_end_to_end_saves_batch_and_rejects_fake_id(tmp_path: Path) -> None:
    model = FakeModel(
        {
            "high_affinity": {"candidate_id": 1, "reason": GOOD},
            "creator_tone": {"candidate_id": 999, "reason": "Invented."},
            "wildcard": {"candidate_id": 2, "reason": "Stone Choir, rated 8.1, from Quiet Harbor."},
        }
    )
    tmdb = FakeTmdb()
    api, db = _app(tmp_path, model, tmdb)
    result = api.picks()
    assert result["error"] == ""
    assert [(p["slot"], p["title"], p["reason_by"]) for p in result["picks"]] == [
        ("Most like your library", "Glass Floor", "model"),
        ("Same people or feel", "Loud Sequel", "code"),
        ("Wildcard", "Stone Choir", "model"),
    ]
    assert "<candidate_data>" in model.asked[0][1]["content"]
    assert _rows(db, "SELECT number, title, status FROM candidates ORDER BY number") == [
        (1, "Glass Floor", "picked"),
        (2, "Stone Choir", "picked"),
        (3, "Loud Sequel", "picked"),
    ]
    assert _rows(db, "SELECT slot_type, llm_model, reason_by FROM picks ORDER BY rank_order") == [
        ("high_affinity", "fake-model", "model"),
        ("creator_tone", "fake-model", "code"),
        ("wildcard", "fake-model", "model"),
    ]
    fetched = len(tmdb.asked)
    api.picks()  # second batch: every title comes from the cache
    assert len(tmdb.asked) == fetched
    assert len(_rows(db, "SELECT DISTINCT batch_id FROM picks")) == 2


def test_picks_without_the_model_are_plain_code(tmp_path: Path) -> None:
    api, db = _app(tmp_path, FakeModel(fail=True))
    result = api.picks()
    assert result["error"] == NO_MODEL
    assert [p["reason_by"] for p in result["picks"]] == ["code", "code", "code"]
    assert _rows(db, "SELECT DISTINCT llm_model FROM picks") == [("",)]


def test_picks_need_looked_up_titles(tmp_path: Path) -> None:
    api = Api(tmp_path / "dl", tmp_path / "c.db", titles=FakeTmdb, model=FakeModel())
    assert api.picks() == {"error": NO_SEEDS, "picks": []}


@pytest.mark.parametrize("error", [KeyMissing("none"), EnrichError("HTTP 500")])
def test_picks_without_tmdb(tmp_path: Path, error: Exception) -> None:
    def broken(kind: str, tmdb_id: int) -> TitleInfo | None:
        raise error

    api, _ = _app(tmp_path, FakeModel(), broken)
    result = api.picks()
    assert result["picks"] == [] and "TMDB" in result["error"]
