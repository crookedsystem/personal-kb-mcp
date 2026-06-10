import re
from hashlib import sha256
from typing import Final

from common.model import FrozenModel

FRONTMATTER_DELIMITER: Final = "---"
FRONTMATTER_CLOSING_DELIMITER: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(FRONTMATTER_DELIMITER)}(?:\r?\n|\Z)",
    re.MULTILINE,
)
PROVENANCE_PREFIX: Final = "<!-- kb-provenance:"


class ParsedNote(FrozenModel):
    """Markdown note split into optional raw frontmatter and body text."""

    frontmatter: str | None
    body: str


def compute_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def parse_note(raw_note: str) -> ParsedNote:
    if raw_note.startswith(f"{FRONTMATTER_DELIMITER}\r\n"):
        frontmatter_start = len(f"{FRONTMATTER_DELIMITER}\r\n")
    elif raw_note.startswith(f"{FRONTMATTER_DELIMITER}\n"):
        frontmatter_start = len(f"{FRONTMATTER_DELIMITER}\n")
    else:
        return ParsedNote(frontmatter=None, body=raw_note)

    closing_match = FRONTMATTER_CLOSING_DELIMITER.search(raw_note[frontmatter_start:])
    if closing_match is None:
        return ParsedNote(frontmatter=None, body=raw_note)

    frontmatter_end = frontmatter_start + closing_match.start()
    frontmatter = (
        raw_note[frontmatter_start:frontmatter_end].removesuffix("\r\n").removesuffix("\n")
    )
    body_start = frontmatter_start + closing_match.end()
    return ParsedNote(frontmatter=frontmatter, body=raw_note[body_start:])


def append_provenance_trailer(
    content: str,
    *,
    source_hash: str,
    operation: str,
    actor: str,
) -> str:
    content_with_newline = content if content.endswith("\n") else f"{content}\n"
    trailer = (
        f"{PROVENANCE_PREFIX} source_hash={source_hash}; operation={operation}; actor={actor} -->\n"
    )
    return f"{content_with_newline}{trailer}"
