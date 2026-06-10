from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import ConfigDict, Field
from yaml.error import YAMLError

from common.model import FrozenModel
from vault.entity.vault_note import compute_sha256, parse_note
from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository

IssueSeverity = Literal["error", "warning"]

_SYNTHESIZED_TYPE_BY_DIR: dict[str, set[str]] = {
    "entities": {"entity"},
    "concepts": {"concept", "summary"},
    "comparisons": {"comparison"},
    "queries": {"query", "summary"},
}
_SYNTHESIZED_DIRS = frozenset(_SYNTHESIZED_TYPE_BY_DIR)
_META_NOTE_PATHS = frozenset({"index.md", "log.md"})
_REQUIRED_SYNTH_FIELDS = (
    "title",
    "created",
    "updated",
    "type",
    "tags",
    "sources",
    "confidence",
    "contested",
)
_REQUIRED_RAW_FIELDS = ("source_url", "ingested", "sha256")
_DEFAULT_ALLOWED_TYPES = ("entity", "concept", "comparison", "query", "summary")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TAG_TAXONOMY_HEADING = re.compile(r"^##\s+Tag taxonomy\s*$", re.IGNORECASE)
_LEVEL_TWO_HEADING = re.compile(r"^##\s+")


class SchemaValidationIssue(FrozenModel):
    code: str
    path: str
    message: str
    severity: IssueSeverity = "error"
    field: str | None = None
    value: str | None = None


class ValidationSummary(FrozenModel):
    missing_frontmatter: int = 0
    missing_required_fields: int = 0
    unknown_tags: int = 0
    invalid_type_for_path: int = 0
    raw_missing_sha256: int = 0
    raw_sha256_mismatch: int = 0
    empty_sources: int = 0
    issue_count: int = 0


class VaultValidationResult(FrozenModel):
    issues: list[SchemaValidationIssue] = Field(default_factory=list)
    summary: ValidationSummary = Field(default_factory=ValidationSummary)


class ParsedWikiSchema(FrozenModel):
    schema_parse_ok: bool
    allowed_types: list[str]
    required_synthesized_frontmatter: list[str]
    required_raw_frontmatter: list[str]
    tag_taxonomy: dict[str, list[str]] = Field(default_factory=dict)
    allowed_tags: list[str] = Field(default_factory=list)


class WikiContextSummary(FrozenModel):
    total_notes: int
    synthesized_pages: int
    raw_sources: int
    last_log_entries: int


class WikiContextHealth(FrozenModel):
    schema_parse_ok: bool
    unknown_tag_count: int
    missing_frontmatter_count: int


class WikiContext(FrozenModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, populate_by_name=True)

    schema_text: str = Field(alias="schema")
    index: str
    recent_log: str
    parsed_schema: ParsedWikiSchema
    summary: WikiContextSummary
    health: WikiContextHealth


class TaxonomyReconcileResult(FrozenModel):
    dry_run: bool
    unknown_tags: list[str]
    tag_usage_counts: dict[str, int]
    planned_changes: list[str]
    changed_files: list[str]


class SchemaValidationError(ValueError):
    """Raised when note content violates the vault schema write contract."""

    def __init__(self, issues: list[SchemaValidationIssue]) -> None:
        self.issues = issues
        payload = {
            "code": "schema_validation_failed",
            "message": "Note violates LLM Wiki schema",
            "issues": [issue.model_dump(exclude_none=True) for issue in issues],
        }
        super().__init__(json.dumps(payload, ensure_ascii=False))


class VaultSchemaService(FrozenModel):
    note_repository: VaultNoteRepository

    def validate_write(self, note_path: str, content: str) -> VaultValidationResult:
        issues = self._validate_write_issues(note_path, content)
        return _validation_result(issues)

    def ensure_valid_write(self, note_path: str, content: str) -> None:
        result = self.validate_write(note_path, content)
        if result.issues:
            raise SchemaValidationError(result.issues)

    def validate_vault(self, *, include_raw: bool = True) -> VaultValidationResult:
        issues: list[SchemaValidationIssue] = []
        schema_path = self.note_repository.vault_root / "SCHEMA.md"
        if schema_path.exists():
            issues.extend(self._validate_schema_note(schema_path.read_text(encoding="utf-8")))
        else:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing",
                    path="SCHEMA.md",
                    field="SCHEMA.md",
                    message="Vault schema file is required before validating wiki pages",
                )
            )

        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if relative_path == "SCHEMA.md" or _is_meta_note_path(relative_path):
                continue
            if _is_raw_path(relative_path):
                if include_raw:
                    issues.extend(
                        self._validate_raw_note(relative_path, path.read_text(encoding="utf-8"))
                    )
                continue
            if _is_synthesized_path(relative_path):
                issues.extend(
                    self._validate_synthesized_note(
                        relative_path,
                        path.read_text(encoding="utf-8"),
                        self._parsed_schema(),
                    )
                )
                continue
            issues.append(
                SchemaValidationIssue(
                    code="unsupported_note_path",
                    path=relative_path,
                    field="note_path",
                    value=relative_path,
                    message=(
                        "Note path must be SCHEMA.md, index.md, log.md, raw/**, "
                        "entities/**, concepts/**, comparisons/**, queries/**, or _meta/**"
                    ),
                )
            )
        return _validation_result(issues)

    def wiki_context(
        self,
        *,
        recent_log_lines: int = 30,
        include_schema_rules: bool = True,
        include_index: bool = True,
    ) -> WikiContext:
        _ = include_schema_rules
        schema_text = self._read_optional_note("SCHEMA.md")
        index_text = self._read_optional_note("index.md") if include_index else ""
        log_text = self._read_optional_note("log.md")
        recent_log = _tail_nonempty_lines(log_text, recent_log_lines)
        parsed_schema = parse_schema_document(schema_text)
        validation = self.validate_vault()
        markdown_notes = self.note_repository.markdown_notes()
        relative_paths = [self.note_repository.relative_path(path) for path in markdown_notes]
        return WikiContext(
            schema=schema_text,
            index=index_text,
            recent_log=recent_log,
            parsed_schema=parsed_schema,
            summary=WikiContextSummary(
                total_notes=len(relative_paths),
                synthesized_pages=sum(1 for path in relative_paths if _is_synthesized_path(path)),
                raw_sources=sum(1 for path in relative_paths if _is_raw_path(path)),
                last_log_entries=len(recent_log.splitlines()) if recent_log else 0,
            ),
            health=WikiContextHealth(
                schema_parse_ok=parsed_schema.schema_parse_ok,
                unknown_tag_count=validation.summary.unknown_tags,
                missing_frontmatter_count=validation.summary.missing_frontmatter,
            ),
        )

    def reconcile_taxonomy(
        self,
        *,
        apply: bool = False,
        decisions: dict[str, object] | None = None,
    ) -> TaxonomyReconcileResult:
        schema = self._parsed_schema()
        tag_usage = self._tag_usage_counts()
        decisions = decisions or {}
        add_tags = sorted(_string_list(decisions.get("add")))
        rename_tags = _string_mapping(decisions.get("rename"))
        remove_tags = set(_string_list(decisions.get("remove")))

        allowed_after_add = set(schema.allowed_tags) | set(add_tags) | set(rename_tags.values())
        unknown_tags = sorted(tag for tag in tag_usage if tag not in schema.allowed_tags)
        planned_changes: list[str] = []
        changed_files: list[str] = []

        taxonomy_tags_to_add = sorted(
            {tag for tag in [*add_tags, *rename_tags.values()] if tag not in schema.allowed_tags}
        )
        for tag in taxonomy_tags_to_add:
            planned_changes.append(f"add taxonomy tag: {tag}")
        for old_tag, new_tag in sorted(rename_tags.items()):
            planned_changes.append(f"rename tag: {old_tag} -> {new_tag}")
        for tag in sorted(remove_tags):
            planned_changes.append(f"remove tag: {tag}")

        if apply:
            schema_path = self.note_repository.vault_root / "SCHEMA.md"
            if taxonomy_tags_to_add:
                schema_path.write_text(
                    _schema_with_added_tags(
                        schema_path.read_text(encoding="utf-8"), taxonomy_tags_to_add
                    ),
                    encoding="utf-8",
                )
                changed_files.append("SCHEMA.md")

            for path in self.note_repository.markdown_notes():
                relative_path = self.note_repository.relative_path(path)
                if not _is_synthesized_path(relative_path):
                    continue
                content = path.read_text(encoding="utf-8")
                rewritten = _rewrite_frontmatter_tags(content, rename_tags, remove_tags)
                if rewritten != content:
                    path.write_text(rewritten, encoding="utf-8")
                    changed_files.append(relative_path)

        unresolved_unknown_tags = sorted(tag for tag in tag_usage if tag not in allowed_after_add)
        return TaxonomyReconcileResult(
            dry_run=not apply,
            unknown_tags=unknown_tags if not apply else unresolved_unknown_tags,
            tag_usage_counts=tag_usage,
            planned_changes=planned_changes,
            changed_files=changed_files,
        )

    def _validate_write_issues(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        if note_path == "SCHEMA.md":
            return self._validate_schema_note(content)
        if _is_meta_note_path(note_path):
            return []
        if _is_raw_path(note_path):
            return self._validate_raw_note(note_path, content)
        if _is_synthesized_path(note_path):
            return self._validate_synthesized_note(note_path, content, self._parsed_schema())
        if note_path.startswith("_meta/"):
            return []
        return [
            SchemaValidationIssue(
                code="unsupported_note_path",
                path=note_path,
                field="note_path",
                value=note_path,
                message=(
                    "Note path must be SCHEMA.md, index.md, log.md, raw/**, entities/**, "
                    "concepts/**, comparisons/**, queries/**, or _meta/**"
                ),
            )
        ]

    def _validate_schema_note(self, content: str) -> list[SchemaValidationIssue]:
        parsed = parse_schema_document(content)
        issues: list[SchemaValidationIssue] = []
        if "## Frontmatter" not in content:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_frontmatter_section",
                    path="SCHEMA.md",
                    field="Frontmatter",
                    message="SCHEMA.md must define the synthesized page frontmatter contract",
                )
            )
        if not parsed.tag_taxonomy:
            issues.append(
                SchemaValidationIssue(
                    code="schema_missing_tag_taxonomy",
                    path="SCHEMA.md",
                    field="Tag taxonomy",
                    message="SCHEMA.md must define a Tag taxonomy section before tags are used",
                )
            )
        return issues

    def _validate_synthesized_note(
        self,
        note_path: str,
        content: str,
        schema: ParsedWikiSchema,
    ) -> list[SchemaValidationIssue]:
        frontmatter, _body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in _REQUIRED_SYNTH_FIELDS:
            if field_name not in frontmatter:
                issues.append(
                    SchemaValidationIssue(
                        code="missing_required_field",
                        path=note_path,
                        field=field_name,
                        message=f"Synthesized pages must include frontmatter field: {field_name}",
                    )
                )

        page_type = _scalar_string(frontmatter.get("type"))
        if page_type is not None:
            if page_type not in schema.allowed_types:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message="Page type is not declared by SCHEMA.md allowed type values",
                    )
                )
            allowed_types_for_path = _allowed_types_for_path(note_path)
            if allowed_types_for_path and page_type not in allowed_types_for_path:
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_type_for_path",
                        path=note_path,
                        field="type",
                        value=page_type,
                        message=(
                            f"Path {note_path} only allows type values: "
                            f"{', '.join(sorted(allowed_types_for_path))}"
                        ),
                    )
                )

        for field_name in ("created", "updated"):
            date_value = _date_string(frontmatter.get(field_name))
            if field_name in frontmatter and (
                date_value is None or not _DATE_PATTERN.match(date_value)
            ):
                issues.append(
                    SchemaValidationIssue(
                        code="invalid_date",
                        path=note_path,
                        field=field_name,
                        value=str(frontmatter.get(field_name)),
                        message=f"{field_name} must use YYYY-MM-DD format",
                    )
                )

        tags = _frontmatter_list(frontmatter.get("tags"))
        if "tags" in frontmatter and tags is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="tags",
                    message="tags must be a YAML list",
                )
            )
        for tag in tags or []:
            if tag not in schema.allowed_tags:
                issues.append(
                    SchemaValidationIssue(
                        code="unknown_tag",
                        path=note_path,
                        field="tags",
                        value=tag,
                        message="Tag is not declared in SCHEMA.md taxonomy",
                    )
                )

        sources = _frontmatter_list(frontmatter.get("sources"))
        if "sources" in frontmatter and sources is None:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_field_type",
                    path=note_path,
                    field="sources",
                    message="sources must be a YAML list",
                )
            )
        elif sources == []:
            issues.append(
                SchemaValidationIssue(
                    code="empty_sources",
                    path=note_path,
                    field="sources",
                    message="sources must include at least one raw note path or source URL",
                )
            )

        confidence = _scalar_string(frontmatter.get("confidence"))
        if confidence is not None and confidence not in {"high", "medium", "low"}:
            issues.append(
                SchemaValidationIssue(
                    code="invalid_confidence",
                    path=note_path,
                    field="confidence",
                    value=confidence,
                    message="confidence must be one of: high, medium, low",
                )
            )
        contested = frontmatter.get("contested")
        if "contested" in frontmatter and not isinstance(contested, bool):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_contested",
                    path=note_path,
                    field="contested",
                    value=str(contested),
                    message="contested must be a YAML boolean",
                )
            )
        return issues

    def _validate_raw_note(self, note_path: str, content: str) -> list[SchemaValidationIssue]:
        frontmatter, body, issues = _frontmatter_mapping(note_path, content)
        if frontmatter is None:
            return issues

        for field_name in _REQUIRED_RAW_FIELDS:
            if field_name not in frontmatter:
                code = f"raw_missing_{field_name}"
                issues.append(
                    SchemaValidationIssue(
                        code=code,
                        path=note_path,
                        field=field_name,
                        message=f"Raw notes must include frontmatter field: {field_name}",
                    )
                )

        ingested = _date_string(frontmatter.get("ingested"))
        if "ingested" in frontmatter and (ingested is None or not _DATE_PATTERN.match(ingested)):
            issues.append(
                SchemaValidationIssue(
                    code="invalid_ingested_date",
                    path=note_path,
                    field="ingested",
                    value=str(frontmatter.get("ingested")),
                    message="ingested must use YYYY-MM-DD format",
                )
            )

        if not body.strip():
            issues.append(
                SchemaValidationIssue(
                    code="raw_empty_body",
                    path=note_path,
                    field="body",
                    message="Raw note body must not be empty",
                )
            )

        expected_hash = _scalar_string(frontmatter.get("sha256"))
        if expected_hash is not None:
            actual_hash = compute_sha256(body)
            if expected_hash != actual_hash:
                issues.append(
                    SchemaValidationIssue(
                        code="raw_sha256_mismatch",
                        path=note_path,
                        field="sha256",
                        value=expected_hash,
                        message="raw sha256 must equal SHA-256 of the body after frontmatter",
                    )
                )
        return issues

    def _parsed_schema(self) -> ParsedWikiSchema:
        return parse_schema_document(self._read_optional_note("SCHEMA.md"))

    def _read_optional_note(self, relative_path: str) -> str:
        path = self.note_repository.vault_root / relative_path
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _tag_usage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in self.note_repository.markdown_notes():
            relative_path = self.note_repository.relative_path(path)
            if not _is_synthesized_path(relative_path):
                continue
            frontmatter, _body, _issues = _frontmatter_mapping(
                relative_path,
                path.read_text(encoding="utf-8"),
            )
            if frontmatter is None:
                continue
            tags = _frontmatter_list(frontmatter.get("tags")) or []
            for tag in tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items()))


def parse_schema_document(content: str) -> ParsedWikiSchema:
    tag_taxonomy = _extract_tag_taxonomy(content)
    allowed_tags = sorted({tag for tags in tag_taxonomy.values() for tag in tags})
    allowed_types = _extract_allowed_types(content) or list(_DEFAULT_ALLOWED_TYPES)
    return ParsedWikiSchema(
        schema_parse_ok=bool(content and tag_taxonomy),
        allowed_types=allowed_types,
        required_synthesized_frontmatter=list(_REQUIRED_SYNTH_FIELDS),
        required_raw_frontmatter=list(_REQUIRED_RAW_FIELDS),
        tag_taxonomy=tag_taxonomy,
        allowed_tags=allowed_tags,
    )


def _frontmatter_mapping(
    note_path: str,
    content: str,
) -> tuple[dict[str, Any] | None, str, list[SchemaValidationIssue]]:
    parsed = parse_note(content)
    if parsed.frontmatter is None:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="missing_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="Markdown note must start with YAML frontmatter delimited by ---",
                )
            ],
        )
    try:
        loaded = yaml.safe_load(parsed.frontmatter) or {}
    except YAMLError as error:
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message=f"YAML frontmatter could not be parsed: {error}",
                )
            ],
        )
    if not isinstance(loaded, dict):
        return (
            None,
            parsed.body,
            [
                SchemaValidationIssue(
                    code="invalid_yaml_frontmatter",
                    path=note_path,
                    field="frontmatter",
                    message="YAML frontmatter must be a mapping/object",
                )
            ],
        )
    return cast(dict[str, Any], loaded), parsed.body, []


def _validation_result(issues: list[SchemaValidationIssue]) -> VaultValidationResult:
    return VaultValidationResult(
        issues=issues,
        summary=ValidationSummary(
            missing_frontmatter=_count_code(issues, "missing_frontmatter"),
            missing_required_fields=_count_code(issues, "missing_required_field"),
            unknown_tags=_count_code(issues, "unknown_tag"),
            invalid_type_for_path=_count_code(issues, "invalid_type_for_path"),
            raw_missing_sha256=_count_code(issues, "raw_missing_sha256"),
            raw_sha256_mismatch=_count_code(issues, "raw_sha256_mismatch"),
            empty_sources=_count_code(issues, "empty_sources"),
            issue_count=len(issues),
        ),
    )


def _count_code(issues: list[SchemaValidationIssue], code: str) -> int:
    return sum(1 for issue in issues if issue.code == code)


def _extract_allowed_types(content: str) -> list[str]:
    match = re.search(r"Allowed `type` values:\s*([^\n]+)", content)
    if match is None:
        return []
    return [
        token
        for token in _extract_tags_from_text(match.group(1))
        if token in _DEFAULT_ALLOWED_TYPES
    ]


def _extract_tag_taxonomy(content: str) -> dict[str, list[str]]:
    lines = content.splitlines()
    taxonomy_lines: list[str] = []
    in_taxonomy = False
    for line in lines:
        if _TAG_TAXONOMY_HEADING.match(line.strip()):
            in_taxonomy = True
            continue
        if in_taxonomy and _LEVEL_TWO_HEADING.match(line.strip()):
            break
        if in_taxonomy:
            taxonomy_lines.append(line)

    taxonomy: dict[str, list[str]] = {}
    current_section = "General"
    in_fence = False
    for raw_line in taxonomy_lines:
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#"):
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            current_section = stripped[:-1].strip() or current_section
            taxonomy.setdefault(current_section, [])
            continue
        if not stripped.startswith("-"):
            continue

        item = stripped[1:].strip()
        if not item or item.startswith("["):
            continue
        values = item
        if ":" in item:
            raw_section, values = item.split(":", 1)
            current_section = raw_section.strip().strip("`") or current_section
        tags = _extract_tags_from_text(values)
        if not tags:
            continue
        section_tags = taxonomy.setdefault(current_section, [])
        for tag in tags:
            if tag not in section_tags:
                section_tags.append(tag)

    return {section: sorted(tags) for section, tags in taxonomy.items() if tags}


def _extract_tags_from_text(text: str) -> list[str]:
    code_tags = [tag for tag in re.findall(r"`([^`]+)`", text) if _TAG_PATTERN.match(tag)]
    if code_tags:
        return code_tags

    candidates = [part.strip().strip("`.;") for part in text.split(",")]
    if len(candidates) == 1:
        single = candidates[0]
        return [single] if _TAG_PATTERN.match(single) else []
    return [candidate for candidate in candidates if _TAG_PATTERN.match(candidate)]


def _allowed_types_for_path(note_path: str) -> set[str]:
    first_part = Path(note_path).parts[0]
    return _SYNTHESIZED_TYPE_BY_DIR.get(first_part, set())


def _is_synthesized_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] in _SYNTHESIZED_DIRS


def _is_raw_path(note_path: str) -> bool:
    parts = Path(note_path).parts
    return bool(parts) and parts[0] == "raw"


def _is_meta_note_path(note_path: str) -> bool:
    return note_path in _META_NOTE_PATHS or note_path.startswith("_meta/")


def _scalar_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _date_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    return None


def _frontmatter_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        result.append(item)
    return result


def _tail_nonempty_lines(content: str, line_count: int) -> str:
    lines = [line for line in content.splitlines() if line.strip()]
    if line_count <= 0:
        return ""
    return "\n".join(lines[-line_count:])


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, mapped_value in value.items():
        if isinstance(key, str) and isinstance(mapped_value, str):
            result[key] = mapped_value
    return result


def _schema_with_added_tags(content: str, tags: list[str]) -> str:
    tags_to_add = [tag for tag in tags if _TAG_PATTERN.match(tag)]
    if not tags_to_add:
        return content
    addition = f"- Added: {', '.join(tags_to_add)}"
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if _TAG_TAXONOMY_HEADING.match(line.strip()):
            insert_at = index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            lines.insert(insert_at, addition)
            return "\n".join(lines) + "\n"
    return f"{content.rstrip()}\n\n## Tag taxonomy\n{addition}\n"


def _rewrite_frontmatter_tags(
    content: str,
    rename_tags: dict[str, str],
    remove_tags: set[str],
) -> str:
    if not rename_tags and not remove_tags:
        return content
    frontmatter, body, issues = _frontmatter_mapping("<rewrite>", content)
    if frontmatter is None or issues:
        return content
    tags = _frontmatter_list(frontmatter.get("tags"))
    if tags is None:
        return content
    rewritten_tags: list[str] = []
    for tag in tags:
        rewritten = rename_tags.get(tag, tag)
        if rewritten in remove_tags:
            continue
        if rewritten not in rewritten_tags:
            rewritten_tags.append(rewritten)
    if rewritten_tags == tags:
        return content
    frontmatter["tags"] = rewritten_tags
    dumped_frontmatter = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{dumped_frontmatter}---\n{body}"
