"""Split source files into meaningful chunks for embedding."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Extensions to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".c", ".cpp", ".h",
    ".rb", ".php", ".swift", ".kt",
    ".yaml", ".yml", ".toml", ".json",
    ".md", ".txt", ".cfg", ".ini",
    ".sh", ".bash", ".dockerfile",
}

# Directories to skip
SKIP_DIRS = {
    ".git", ".convaier", "__pycache__", "node_modules",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".egg-info",
}

MAX_CHUNK_LINES = 60
OVERLAP_LINES = 5


@dataclass
class Chunk:
    file: str
    start_line: int
    end_line: int
    content: str


def _should_index(path: Path) -> bool:
    if path.suffix.lower() not in CODE_EXTENSIONS:
        return False
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    return True


def _split_by_definitions(lines: list[str]) -> list[tuple[int, int]]:
    """Try to split on class/function boundaries."""
    boundaries = []
    # Match common definition patterns
    pattern = re.compile(
        r"^(class |def |function |const |let |var |export |public |private |func |fn )"
    )
    for i, line in enumerate(lines):
        stripped = line.strip()
        if pattern.match(stripped) and i > 0:
            boundaries.append(i)

    if not boundaries:
        return []

    ranges = []
    for idx in range(len(boundaries)):
        start = boundaries[idx]
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(lines)
        # Cap chunk size
        if end - start > MAX_CHUNK_LINES:
            end = start + MAX_CHUNK_LINES
        ranges.append((start, end))

    # Include header (imports, etc.) if first definition doesn't start at line 0
    if boundaries[0] > 0:
        ranges.insert(0, (0, min(boundaries[0], MAX_CHUNK_LINES)))

    return ranges


def _split_fixed(lines: list[str]) -> list[tuple[int, int]]:
    """Fall back to fixed-size chunks with overlap."""
    ranges = []
    i = 0
    while i < len(lines):
        end = min(i + MAX_CHUNK_LINES, len(lines))
        ranges.append((i, end))
        i = end - OVERLAP_LINES if end < len(lines) else end
    return ranges


def chunk_file(path: Path, project_root: Path) -> list[Chunk]:
    """Split a file into chunks."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    lines = content.splitlines()
    if not lines:
        return []

    rel_path = str(path.relative_to(project_root))

    # Small file — single chunk
    if len(lines) <= MAX_CHUNK_LINES:
        return [Chunk(file=rel_path, start_line=1, end_line=len(lines), content=content)]

    # Try definition-based splitting
    ranges = _split_by_definitions(lines)
    if not ranges:
        ranges = _split_fixed(lines)

    chunks = []
    for start, end in ranges:
        chunk_content = "\n".join(lines[start:end])
        if chunk_content.strip():
            chunks.append(Chunk(
                file=rel_path,
                start_line=start + 1,
                end_line=end,
                content=chunk_content,
            ))
    return chunks


def collect_files(project_root: Path) -> list[Path]:
    """Collect all indexable files."""
    files = []
    for path in project_root.rglob("*"):
        if path.is_file() and _should_index(path.relative_to(project_root)):
            files.append(path)
    return sorted(files)
