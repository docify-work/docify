"""Policy checks, issue path detection, insights health (D66)."""

from __future__ import annotations

import uuid

import pytest

from docify import checks
from docify.db.models import Policy
from docify.insights import _health
from docify.issues import mentioned_paths


def _policy(key: str) -> checks.CompiledPolicy:
    t = checks.TEMPLATES[key]
    p = Policy(id=uuid.uuid4(), name=t["name"], kind=t["kind"], pattern=t["pattern"], severity=t["severity"],
               paths=t["paths"] or None, enabled=True, template=key)
    return checks.compile_policies([p])[0]


def test_added_lines_tracks_new_file_line_numbers() -> None:
    patch = "@@ -1,3 +1,4 @@\n line one\n-old two\n+new two\n+new three\n line four\n\\ No newline at end of file"
    assert checks.added_lines(patch) == [(2, "new two"), (3, "new three")]
    assert checks.added_lines("@@ -10,0 +20,2 @@\n+a\n+b") == [(20, "a"), (21, "b")]
    assert checks.added_lines(None) == []


@pytest.mark.parametrize("line", ["const MODEL = 'gpt-4o-mini'", "Powered by Claude Sonnet", "use gemini 2.5",
                                  "llama3 runs locally", "model: apac.amazon.nova-lite-v1:0"])
def test_ai_model_names_are_flagged(line: str) -> None:
    hits = checks.scan_lines([_policy("ai_models")], "src/app.ts", [(1, line)])
    assert hits and hits[0].policy.severity == "medium"


@pytest.mark.parametrize("line", ["const total = splitBill(1200, 10, 3)", "the novel was great", "GPTs are cool?",
                                  "claudette = 1"])
def test_normal_code_is_not_flagged(line: str) -> None:
    assert checks.scan_lines([_policy("ai_models")], "a.py", [(1, line)]) == []


def test_secrets_are_redacted_before_storing() -> None:
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    hits = checks.scan_lines([_policy("secrets")], "deploy.sh", [(4, f"export AWS_ACCESS_KEY_ID={key}")])
    assert hits and key not in hits[0].snippet and key not in hits[0].match
    assert "[redacted]" in hits[0].snippet
    pw = checks.scan_lines([_policy("secrets")], "cfg.py", [(1, 'password = "hunter2hunter2"')])
    assert pw and "hunter2hunter2" not in pw[0].snippet


def test_path_globs_limit_a_policy() -> None:
    debug = _policy("debug")
    assert checks.scan_lines([debug], "web/app.tsx", [(1, "console.log(x)")])
    assert checks.scan_lines([debug], "backend/app.py", [(1, "console.log(x)")]) == []
    assert checks.path_matches(None, "anything")
    assert checks.path_matches("docs/*", "docs/a.md") and not checks.path_matches("docs/*", "src/a.md")


def test_terms_policy_matches_whole_words_case_insensitive() -> None:
    rx = checks.compile_pattern("terms", "TODO\nFIXME")
    assert rx.search("# todo: later") and rx.search("FIXME now")
    assert not rx.search("todos_list = []")


@pytest.mark.parametrize("pattern", ["(a+)+$", "(x*)*", "", "x" * 600, "([unclosed"])
def test_dangerous_or_invalid_patterns_are_rejected(pattern: str) -> None:
    with pytest.raises(checks.PolicyError):
        checks.compile_pattern("regex", pattern)


def test_fingerprint_ignores_whitespace_but_not_location() -> None:
    pid = uuid.uuid4()
    assert checks.fingerprint(pid, "a.py", "x  =  1") == checks.fingerprint(pid, "a.py", "x = 1")
    assert checks.fingerprint(pid, "a.py", "x = 1") != checks.fingerprint(pid, "b.py", "x = 1")


def test_mentioned_paths() -> None:
    text = "Reset breaks in script.js:42 and src/app/main.py; see README.md. Not a path: e.g. 1.5"
    assert mentioned_paths(text) == ["script.js", "src/app/main.py", "README.md"]


def test_health_score_explains_itself() -> None:
    good = _health(2, 2, 3, 3, {}, 0)
    assert good["score"] == 100 and good["grade"] == "A"
    bad = _health(120, 1, 1, 1, {"critical": 2}, 2)
    assert bad["score"] < 50 and len(bad["notes"]) >= 4
    assert _health(None, 0, 0, 0, {}, 0)["grade"] == "n/a"


def test_rows_have_uniform_keys_for_multi_row_insert() -> None:
    # Regression: scan rows with and without blame attribution must render the same INSERT VALUES shape.
    from docify.checks import _row
    from docify.db.models import Repository

    repo = Repository(id=uuid.uuid4(), workspace_id=uuid.uuid4())
    hit = checks.scan_lines([_policy("ai_models")], "a.ts", [(1, "gpt-4o")])[0]
    with_author = _row(repo, hit, "scan", commit_sha="c" * 40, author_login="grace")
    without = _row(repo, hit, "scan")
    assert with_author.keys() == without.keys() and without["author_login"] is None
