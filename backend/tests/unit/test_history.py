"""Git-history helpers for chat (D63)."""

from __future__ import annotations

import pytest

from docify.ai import history
from docify.ai.rag import _terms


@pytest.mark.parametrize("q", ["who created this new feature", "When was the reset button added?",
                               "Who wrote auth.py", "what changed in the latest commit", "who is the owner"])
def test_history_questions(q: str) -> None:
    assert history.is_history_question(q)


@pytest.mark.parametrize("q", ["How are passwords hashed?", "What does the Reset button do?"])
def test_plain_code_questions(q: str) -> None:
    assert not history.is_history_question(q)


def test_followup_detection() -> None:
    q = "who created this new feature"
    assert history.is_followup(q, len(_terms(q)))
    q = "How does the rounding of each share in splitBill handle paise values"
    assert not history.is_followup(q, len(_terms(q)))


@pytest.mark.parametrize(("msg", "n"), [("Merge pull request #12 from x/y\n\nbody", 12), ("Add reset (#2)", 2),
                                        ("Fix #3 in body", None), ("", None)])
def test_pr_number(msg: str, n: int | None) -> None:
    assert history.pr_number(msg) == n


def test_parse_ts() -> None:
    assert history.parse_ts("2026-10-05T12:30:00Z").isoformat() == "2026-10-05T12:30:00+00:00"  # type: ignore[union-attr]
    assert history.parse_ts("nope") is None and history.parse_ts(None) is None
