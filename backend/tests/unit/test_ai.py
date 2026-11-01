from __future__ import annotations

import itertools
import math

import pytest

from docify.ai import citations
from docify.ai.budget import TokenMeter, estimate_tokens
from docify.ai.chunking import CODE_LINES, chunk_code, chunk_markdown, path_tokens, split_identifiers
from docify.ai.docgen import Material, _select, docs_to_update, numbered, tree
from docify.ai.fakes import FakeEmbedder, FakeLLM
from docify.ai.llm import Usage, cost_usd
from docify.ai.rag import fts_query


class TestChunking:
    def test_identifier_split(self) -> None:
        out = split_identifiers("def getUserById(user_id): parseHTTPResponse()")
        assert "get user by id" in out
        assert "user id" in out
        assert "parse http response" in out

    def test_small_file_single_chunk(self) -> None:
        pieces = chunk_code("a\nb\nc")
        assert len(pieces) == 1
        assert (pieces[0].start_line, pieces[0].end_line) == (1, 3)

    def test_large_file_overlaps_and_covers(self) -> None:
        text = "\n".join(f"x = {i}" for i in range(200))
        pieces = chunk_code(text)
        assert pieces[0].start_line == 1
        assert pieces[-1].end_line == 200
        for a, b in itertools.pairwise(pieces):
            assert b.start_line <= a.end_line  # overlap, no gaps
        assert all(p.end_line - p.start_line + 1 <= CODE_LINES for p in pieces)

    def test_snaps_to_boundary(self) -> None:
        lines = [f"x{i} = 1" for i in range(55)] + ["def foo():"] + ["    pass"] * 30
        pieces = chunk_code("\n".join(lines))
        assert pieces[0].end_line == 55  # ends right before `def foo`

    def test_hash_ignores_position(self) -> None:
        a = chunk_code("def f():\n    return 1")[0]
        b = chunk_code("def f():\n    return 1")[0]
        assert a.content_hash == b.content_hash

    def test_markdown_by_heading(self) -> None:
        md = "# A\ntext\n## B\nmore\n## C\nend"
        pieces = chunk_markdown(md)
        assert [p.content.split("\n")[0] for p in pieces] == ["# A", "## B", "## C"]

    def test_path_tokens(self) -> None:
        assert path_tokens("src/user_service.py") == "src user service py"


class TestCitations:
    def test_validate_drops_bad(self) -> None:
        text = "See [[a.py:1-5]] and [[b.py:10-12]] and [[a.py:9-99]]."
        out, removed = citations.validate(text, {"a.py": 20})
        assert removed == 2
        assert "[[a.py:1-5]]" in out
        assert "b.py" not in out

    def test_single_line(self) -> None:
        assert citations.extract("x [[p/q.go:7]]") == [("p/q.go", 7, 7)]

    def test_render_permalink(self) -> None:
        out = citations.render("x [[src/a.py:3-4]]", "o/r", "abc")
        assert "https://github.com/o/r/blob/abc/src/a.py#L3-L4" in out


class TestRetrievalHelpers:
    def test_fts_query_or_terms(self) -> None:
        q = fts_query("How does the login auth work?")
        assert q == "auth | login"
        assert fts_query("passwords hashed") == "hash:* | hashed | password:* | passwords"

    def test_fts_query_only_stopwords(self) -> None:
        assert fts_query("how does it work?") is None

    def test_identifier_terms(self) -> None:
        assert "user" in (fts_query("where is getUserById") or "")


class TestCost:
    def test_haiku_small_prompt(self) -> None:
        c = cost_usd("claude-haiku-5-5", Usage(input_tokens=50_000, output_tokens=50_000))
        assert math.isclose(c, 0.03)  # 50k*$0.10/M + 50k*$0.50/M

    def test_haiku_large_prompt_tier(self) -> None:
        c = cost_usd("claude-haiku-5-5", Usage(input_tokens=200_000, output_tokens=0))
        assert math.isclose(c, 0.10)  # 200k * $0.50/M

    def test_cache_read_discount(self) -> None:
        c = cost_usd("claude-sonnet-5-5", Usage(cache_read_tokens=1_000_000))
        assert math.isclose(c, 0.2)

    def test_unknown_model_free(self) -> None:
        assert cost_usd("nope", Usage(input_tokens=10)) == 0

    def test_meter(self) -> None:
        m = TokenMeter(limit=100)
        assert m.can_spend(100)
        m.spend(60)
        assert not m.can_spend(41)
        assert estimate_tokens("abcd" * 10) >= 10


class TestDocgen:
    def test_select_respects_budget(self) -> None:
        mats = [Material("a", "x" * 3200, 0), Material("b", "y" * 3200, 1), Material("c", "z" * 32000, 5)]
        chosen, partial = _select(mats, budget=3000)
        assert [m.path for m in chosen] == ["a", "b"]
        assert partial

    def test_numbered(self) -> None:
        assert numbered("a\nb").splitlines() == ["   1| a", "   2| b"]

    def test_tree(self) -> None:
        t = tree(["src/a/b/c.py", "README.md"])
        assert "src/" in t
        assert "README.md" in t

    def test_update_rule(self) -> None:
        docs = {"overview": ["README.md"], "setup": ["Makefile"], "api": ["app/routes.py"]}
        assert docs_to_update({"app/util.py"}, set(), docs, {"app/routes.py"}) == []
        assert docs_to_update({"app/routes.py"}, set(), docs, {"app/routes.py"}) == ["api"]
        assert set(docs_to_update({"package.json"}, set(), docs, set())) == {"overview", "setup"}
        assert docs_to_update(set(), set(), {}, set()) == ["overview", "setup", "api"]


class TestFakes:
    async def test_embedder_similarity(self) -> None:
        e = FakeEmbedder(dim=256)
        (a, b, c), _ = await e.embed(["password hashing bcrypt", "hash the password with bcrypt", "kafka consumer"],
                                     input_type="document")
        dot = lambda x, y: sum(i * j for i, j in zip(x, y, strict=True))  # noqa: E731
        assert dot(a, b) > dot(a, c)

    async def test_llm_summary_schema(self) -> None:
        r = await FakeLLM().complete(task="summary", model="m", system="", max_tokens=10, output_schema={},
                                     messages=[{"role": "user", "content": "Path: a.py\n\ndef foo(): pass"}])
        assert r.data is not None
        assert r.data["symbols"] == ["foo"]


@pytest.mark.parametrize(("attempts", "low", "high"), [(0, 24, 36), (3, 192, 288), (10, 720, 1080)])
def test_backoff(attempts: int, low: int, high: int) -> None:
    from docify.jobs.service import backoff_s

    for _ in range(20):
        assert low <= backoff_s(attempts) <= high


def test_citation_without_lines_becomes_whole_file_link() -> None:
    # Nova sometimes cites [[path]] without lines; it must never stay as a raw marker (2026-11-01).
    text, removed = citations.validate("Layout: [[README.md]] and [[missing.txt]] here.", {"README.md": 12})
    assert text == "Layout: [[README.md:1-12]] and  here."
    assert removed == 1
    rendered = citations.render(text, "acme/taskly", "a" * 40)
    assert "[`README.md:1-12`](https://github.com/acme/taskly/blob/" in rendered
    assert "[[" not in rendered
