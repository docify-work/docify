from __future__ import annotations

import hashlib
import hmac
import io
import tarfile
from pathlib import Path

import pytest

from docify.github.tarball import iter_tarball
from docify.ingest.filters import content_allowed, is_secret_file, language_for, load_docifyignore, path_allowed
from docify.ingest.normalise import normalise
from docify.ingest.redact import REDACTED, redact
from docify.ingest.verify import verify_signature
from docify.jobs.errors import NonRetryableError


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestVerify:
    def test_valid(self) -> None:
        assert verify_signature("s3cret", b"{}", sign("s3cret", b"{}"))

    @pytest.mark.parametrize("header", [None, "", "sha1=abc", "sha256=deadbeef"])
    def test_invalid(self, header: str | None) -> None:
        assert not verify_signature("s3cret", b"{}", header)

    def test_body_tamper(self) -> None:
        assert not verify_signature("s3cret", b"{ }", sign("s3cret", b"{}"))

    def test_empty_secret_rejects(self) -> None:
        assert not verify_signature("", b"{}", sign("", b"{}"))


class TestNormalise:
    repo = {"id": 1, "default_branch": "main", "full_name": "a/b"}

    def test_push_default_branch(self) -> None:
        msg = normalise("push", "d1", {"ref": "refs/heads/main", "repository": self.repo, "installation": {"id": 9},
                                       "before": "x", "after": "y", "forced": True})
        assert msg is not None
        assert msg["forced"] is True
        assert msg["installation_id"] == 9

    @pytest.mark.parametrize("ref", ["refs/heads/feature", "refs/tags/v1"])
    def test_push_other_refs_ignored(self, ref: str) -> None:
        assert normalise("push", "d", {"ref": ref, "repository": self.repo}) is None

    def test_branch_delete_ignored(self) -> None:
        assert normalise("push", "d", {"ref": "refs/heads/main", "deleted": True, "repository": self.repo}) is None

    def test_repository_edited_only_for_default_branch(self) -> None:
        base = {"action": "edited", "repository": self.repo}
        assert normalise("repository", "d", {**base, "changes": {"description": {}}}) is None
        assert normalise("repository", "d", {**base, "changes": {"default_branch": {"from": "master"}}}) is not None

    def test_unknown_event(self) -> None:
        assert normalise("star", "d", {"action": "created"}) is None

    def test_installation_repositories(self) -> None:
        msg = normalise("installation_repositories", "d", {"action": "removed", "installation": {"id": 3},
                                                            "repositories_removed": [{"id": 5}]})
        assert msg is not None
        assert msg["repos_removed"] == [5]


class TestRedact:
    @pytest.mark.parametrize("secret", [
        "AKIAABCDEFGHIJKLMNOP",
        "ghp_" + "a" * 36,
        "github_pat_" + "A1" * 20,
        "xoxb-1234567890-abcdef",
        "sk-ant-api03-" + "x" * 30,
        "sk_live_" + "a" * 24,
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    ])
    def test_patterns(self, secret: str) -> None:
        out, n = redact(f"value = {secret} # end")
        assert secret not in out
        assert n >= 1

    def test_private_key_block(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        assert redact(text)[0] == REDACTED

    def test_assignment_keeps_key(self) -> None:
        out, _ = redact('DB_PASSWORD = "hunter2-long-secret"')
        assert out == f'DB_PASSWORD = "{REDACTED}"'

    def test_plain_code_untouched(self) -> None:
        code = 'def get_token(user):\n    return tokens[user]\n'
        assert redact(code) == (code, 0)


class TestFilters:
    @pytest.mark.parametrize("path", [
        "node_modules/x/index.js", "package-lock.json", "dist/app.js", "a/b.min.js", "x.map", ".env", ".env.prod",
        "certs/server.pem", "id_rsa", "infra/prod.tfvars", "terraform.tfstate", "logo.png", "src/.venv/lib.py",
    ])
    def test_skipped(self, path: str) -> None:
        assert not path_allowed(path)

    @pytest.mark.parametrize("path", ["src/app.py", ".env.example", "README.md", "infra/x.tfvars.example",
                                      ".github/workflows/ci.yml", "Dockerfile"])
    def test_allowed(self, path: str) -> None:
        assert path_allowed(path)

    def test_docifyignore(self) -> None:
        spec = load_docifyignore("generated/\n*.snap\n")
        assert not path_allowed("generated/x.py", spec)
        assert not path_allowed("a/b.snap", spec)
        assert path_allowed("src/x.py", spec)

    def test_content(self) -> None:
        assert content_allowed(b"hello", 10) == "hello"
        assert content_allowed(b"a\x00b", 10) is None
        assert content_allowed(b"\xff\xfe", 10) is None
        assert content_allowed(b"x" * 11, 10) is None

    def test_language(self) -> None:
        assert language_for("a/b.py") == "python"
        assert language_for("Dockerfile") == "dockerfile"
        assert language_for("x.unknown") is None
        assert is_secret_file("prod.key")
        assert not is_secret_file(".env.example")


def _tar(tmp: Path, members: list[tarfile.TarInfo], data: dict[str, bytes]) -> Path:
    p = tmp / "t.tar.gz"
    with tarfile.open(p, "w:gz") as tar:
        for m in members:
            tar.addfile(m, io.BytesIO(data.get(m.name, b"")) if m.isreg() else None)
    return p


class TestTarball:
    def test_strips_prefix_and_skips_links(self, tmp_path: Path) -> None:
        reg = tarfile.TarInfo("o-r-sha/src/a.py")
        reg.size = 5
        link = tarfile.TarInfo("o-r-sha/evil")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        trav = tarfile.TarInfo("o-r-sha/../../x.py")
        trav.size = 1
        p = _tar(tmp_path, [reg, link, trav], {"o-r-sha/src/a.py": b"hello", "o-r-sha/../../x.py": b"x"})
        out = list(iter_tarball(p, max_file_bytes=100))
        assert [(f.path, f.data) for f in out] == [("src/a.py", b"hello")]

    def test_big_file_yields_empty(self, tmp_path: Path) -> None:
        reg = tarfile.TarInfo("p/big.txt")
        reg.size = 50
        p = _tar(tmp_path, [reg], {"p/big.txt": b"x" * 50})
        assert next(iter_tarball(p, max_file_bytes=10)).data == b""

    def test_member_cap(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import docify.github.tarball as tb

        monkeypatch.setattr(tb, "MAX_MEMBERS", 2)
        members = []
        for i in range(3):
            m = tarfile.TarInfo(f"p/{i}.txt")
            m.size = 1
            members.append(m)
        p = _tar(tmp_path, members, {f"p/{i}.txt": b"x" for i in range(3)})
        with pytest.raises(NonRetryableError):
            list(iter_tarball(p, max_file_bytes=10))
