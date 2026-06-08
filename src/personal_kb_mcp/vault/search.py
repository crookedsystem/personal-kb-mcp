import re
from dataclasses import dataclass
from pathlib import Path

from personal_kb_mcp.vault.notes import compute_sha256
from personal_kb_mcp.vault.paths import DEFAULT_DENIED_NAMES, VaultPathError

QUERY_TOKEN_PATTERN = re.compile(r"[\w가-힣一-龥ぁ-んァ-ン]+", re.UNICODE)
FRONTMATTER_BOUNDARY = "---"
MAX_SEARCH_LIMIT = 50
SYNTHESIZED_PAGE_DIRS = {"concepts", "entities", "comparisons", "queries"}


@dataclass(frozen=True)
class LineMatch:
    line: int
    snippet: str


@dataclass(frozen=True)
class NoteSearchResult:
    path: str
    title: str | None
    page_type: str | None
    tags: list[str]
    score: float
    content_hash: str
    matches: list[LineMatch]


def search_notes(
    vault_root: Path,
    query: str,
    *,
    limit: int = 10,
    path_prefix: str | None = None,
) -> list[NoteSearchResult]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    if not 1 <= limit <= MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SEARCH_LIMIT}")

    root = vault_root.expanduser().resolve()
    search_root = _resolve_path_prefix(root, path_prefix)
    terms = _query_terms(normalized_query)
    results: list[NoteSearchResult] = []

    for note_path in _markdown_notes(root, search_root):
        relative_path = note_path.relative_to(root).as_posix()
        content = note_path.read_text(encoding="utf-8")
        metadata = _extract_metadata(content)
        score = _score_note(relative_path, content, metadata, normalized_query, terms)
        if score <= 0:
            continue
        results.append(
            NoteSearchResult(
                path=relative_path,
                title=metadata.title,
                page_type=metadata.page_type,
                tags=metadata.tags,
                score=round(score, 3),
                content_hash=compute_sha256(content),
                matches=_line_matches(content, normalized_query, terms),
            )
        )

    return sorted(results, key=lambda result: (-result.score, result.path))[:limit]


@dataclass(frozen=True)
class _NoteMetadata:
    title: str | None
    page_type: str | None
    tags: list[str]
    headings: list[str]


def _resolve_path_prefix(root: Path, path_prefix: str | None) -> Path:
    if path_prefix is None or path_prefix.strip() in {"", "."}:
        return root

    relative_prefix = Path(path_prefix)
    if relative_prefix.is_absolute():
        raise VaultPathError("path_prefix must be relative to the vault")

    resolved_prefix = (root / relative_prefix).resolve()
    try:
        resolved_prefix.relative_to(root)
    except ValueError as error:
        raise VaultPathError(f"path_prefix escapes outside vault: {resolved_prefix}") from error

    if _uses_denied_directory(root, resolved_prefix):
        raise VaultPathError("path_prefix uses denied vault directory")
    return resolved_prefix


def _markdown_notes(root: Path, search_root: Path) -> list[Path]:
    if not search_root.exists():
        return []
    if search_root.is_file():
        candidates = [search_root] if search_root.suffix == ".md" else []
    else:
        candidates = list(search_root.rglob("*.md"))
    return sorted(
        path.resolve()
        for path in candidates
        if path.is_file() and not _uses_denied_directory(root, path.resolve())
    )


def _uses_denied_directory(root: Path, path: Path) -> bool:
    return any(part in DEFAULT_DENIED_NAMES for part in path.relative_to(root).parts)


def _query_terms(query: str) -> list[str]:
    terms = [token.lower() for token in QUERY_TOKEN_PATTERN.findall(query) if len(token) > 1]
    return terms or [query.lower()]


def _extract_metadata(content: str) -> _NoteMetadata:
    frontmatter = _frontmatter(content)
    frontmatter_values = _frontmatter_values(frontmatter)
    headings = _headings(content)
    title = frontmatter_values.get("title") or (headings[0] if headings else None)
    return _NoteMetadata(
        title=title,
        page_type=frontmatter_values.get("type"),
        tags=_frontmatter_tags(frontmatter),
        headings=headings,
    )


def _frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_BOUNDARY:
            return "\n".join(lines[1:index])
    return ""


def _frontmatter_values(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        key, separator, raw_value = line.partition(":")
        if separator and raw_value.strip():
            values[key.strip()] = _normalize_frontmatter_scalar(raw_value)
    return values


def _frontmatter_tags(frontmatter: str) -> list[str]:
    lines = frontmatter.splitlines()
    tags: list[str] = []
    for index, line in enumerate(lines):
        key, separator, raw_value = line.partition(":")
        if key.strip() != "tags" or not separator:
            continue
        stripped_value = raw_value.strip()
        if stripped_value.startswith("[") and stripped_value.endswith("]"):
            return [
                _normalize_frontmatter_scalar(part)
                for part in stripped_value[1:-1].split(",")
                if part.strip()
            ]
        for following_line in lines[index + 1 :]:
            stripped_line = following_line.strip()
            if not stripped_line.startswith("-"):
                break
            tag = _normalize_frontmatter_scalar(stripped_line[1:])
            if tag:
                tags.append(tag)
        return tags
    return tags


def _normalize_frontmatter_scalar(raw_value: str) -> str:
    return raw_value.strip().strip("'\"")


def _headings(content: str) -> list[str]:
    headings: list[str] = []
    for line in content.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            heading = stripped_line.lstrip("#").strip()
            if heading:
                headings.append(heading)
    return headings


def _score_note(
    relative_path: str,
    content: str,
    metadata: _NoteMetadata,
    query: str,
    terms: list[str],
) -> float:
    path_lower = relative_path.lower()
    content_lower = content.lower()
    query_lower = query.lower()
    title_lower = (metadata.title or "").lower()
    page_type_lower = (metadata.page_type or "").lower()
    tags_lower = " ".join(metadata.tags).lower()
    headings_lower = "\n".join(metadata.headings).lower()

    score = 0.0
    if query_lower in content_lower:
        score += 5.0
    if query_lower in path_lower:
        score += 8.0
    if query_lower in title_lower:
        score += 12.0

    for term in terms:
        if term in title_lower:
            score += 10.0
        if term in path_lower:
            score += 6.0
        if term in page_type_lower:
            score += 4.0
        if term in tags_lower:
            score += 5.0
        score += min(headings_lower.count(term), 3) * 4.0
        score += min(content_lower.count(term), 10) * 1.0

    score += _structure_boost(relative_path)
    return score


def _structure_boost(relative_path: str) -> float:
    path = Path(relative_path)
    if relative_path == "index.md":
        return 8.0
    if relative_path == "SCHEMA.md":
        return 5.0
    if path.parts and path.parts[0] in SYNTHESIZED_PAGE_DIRS:
        return 2.0
    if path.parts and path.parts[0] == "raw":
        return -10.0
    return 0.0


def _line_matches(content: str, query: str, terms: list[str]) -> list[LineMatch]:
    lines = content.splitlines()
    query_lower = query.lower()
    matches: list[LineMatch] = []
    for index, line in enumerate(lines):
        line_lower = line.lower()
        if query_lower in line_lower or any(term in line_lower for term in terms):
            matches.append(LineMatch(line=index + 1, snippet=_snippet(lines, index)))
        if len(matches) >= 3:
            break

    if matches:
        return matches

    for index, line in enumerate(lines):
        if line.strip():
            return [LineMatch(line=index + 1, snippet=_snippet(lines, index))]
    return []


def _snippet(lines: list[str], center_index: int) -> str:
    start = max(0, center_index - 1)
    end = min(len(lines), center_index + 2)
    snippet = "\n".join(line.strip() for line in lines[start:end] if line.strip())
    return snippet[:500]
