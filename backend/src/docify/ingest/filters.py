"""Which repo files we ingest (Master Doc §9.5)."""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

import pathspec

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", ".next", "__pycache__", ".venv", "venv",
    "coverage", ".terraform", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
}
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock", "go.sum",
    "composer.lock", "Gemfile.lock", "bun.lockb", "Pipfile.lock",
}
SKIP_GLOBS = ("*.min.*", "*.map")
NEVER_INGEST = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "id_ecdsa*", "credentials*",
    "*.tfstate", "*.tfstate.*", "*.tfvars", "*.jks", "*.keystore", ".npmrc", ".pypirc", ".netrc",
)
ALLOW_EXAMPLES = (".env.example", ".env.sample", "*.tfvars.example")
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".jar",
    ".war", ".class", ".so", ".dll", ".dylib", ".exe", ".bin", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3",
    ".mp4", ".mov", ".avi", ".wav", ".sqlite", ".db", ".parquet", ".pyc", ".o", ".a", ".psd", ".svgz",
}

LANGUAGES = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".swift": "swift", ".scala": "scala", ".sh": "shell", ".bash": "shell", ".ps1": "powershell",
    ".sql": "sql", ".md": "markdown", ".rst": "rst", ".txt": "text", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".toml": "toml", ".tf": "terraform", ".hcl": "terraform", ".html": "html", ".css": "css",
    ".scss": "css", ".vue": "vue", ".svelte": "svelte", ".dockerfile": "dockerfile", ".proto": "protobuf",
    ".graphql": "graphql", ".ini": "ini", ".cfg": "ini", ".xml": "xml", ".gradle": "gradle",
}
TEXT_DOC_EXT = {".md", ".rst", ".txt"}


def language_for(path: str) -> str | None:
    p = PurePosixPath(path)
    if p.name == "Dockerfile" or p.name.startswith("Dockerfile."):
        return "dockerfile"
    if p.name in ("Makefile", "justfile"):
        return "make"
    return LANGUAGES.get(p.suffix.lower())


def _match_any(name: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, g) for g in globs)


def is_secret_file(path: str) -> bool:
    name = PurePosixPath(path).name
    if _match_any(name, ALLOW_EXAMPLES):
        return False
    return _match_any(name, NEVER_INGEST)


def path_allowed(path: str, ignore: pathspec.PathSpec | None = None) -> bool:
    """Cheap checks on the path only (before reading content)."""
    parts = PurePosixPath(path).parts
    if any(part in SKIP_DIRS for part in parts[:-1]):
        return False
    name = parts[-1] if parts else ""
    if name in LOCKFILES or _match_any(name, SKIP_GLOBS) or is_secret_file(path):
        return False
    if PurePosixPath(name).suffix.lower() in BINARY_EXT:
        return False
    return not (ignore is not None and ignore.match_file(path))


def content_allowed(data: bytes, max_bytes: int) -> str | None:
    """Returns decoded text, or None if binary / too big / not UTF-8."""
    if len(data) > max_bytes or b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def load_docifyignore(text: str | None) -> pathspec.PathSpec | None:
    if not text:
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", text.splitlines())
