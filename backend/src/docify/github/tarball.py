"""Safe reading of GitHub tarballs (Master Doc §9.3, F17).

We never extract to disk: members are read in streaming mode straight into memory,
so path traversal / symlink tricks can't write anywhere. Caps stop tar bombs.
"""

from __future__ import annotations

import tarfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from docify.jobs.errors import NonRetryableError

MAX_UNCOMPRESSED = 300 * 1024 * 1024
MAX_MEMBERS = 20_000


@dataclass
class TarFile:
    path: str
    data: bytes


def iter_tarball(archive: Path, *, max_file_bytes: int, wanted: set[str] | None = None) -> Iterator[TarFile]:
    """Yield regular files (path without the `owner-repo-sha/` prefix) up to `max_file_bytes`.

    Files above the per-file cap are yielded with empty data so callers can count them.
    """
    total = 0
    members = 0
    with tarfile.open(archive, mode="r|gz") as tar:
        for member in tar:
            members += 1
            if members > MAX_MEMBERS:
                raise NonRetryableError("Repository has too many files.", code="too_large", repo_status="too_large")
            if not member.isreg():  # skip dirs, symlinks, hardlinks, devices
                continue
            parts = PurePosixPath(member.name).parts
            if len(parts) < 2 or any(p in ("..", "") for p in parts) or member.name.startswith("/"):
                continue
            rel = "/".join(parts[1:])
            total += member.size
            if total > MAX_UNCOMPRESSED:
                raise NonRetryableError("Repository is too large once unpacked.", code="too_large",
                                        repo_status="too_large")
            if wanted is not None and rel not in wanted:
                continue
            if member.size > max_file_bytes:
                yield TarFile(rel, b"")
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            yield TarFile(rel, fh.read(max_file_bytes + 1))
