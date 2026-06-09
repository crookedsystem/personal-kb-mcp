"""Centralized prompt and content templates for LLM Wiki agent tooling.

Keep the prose/content here as named ``Final`` constants so the surrounding
logic stays small and the wording can be reviewed in one place. Use ``.format``
placeholders for runtime values; never interpolate logic into these strings.
"""

from __future__ import annotations

from prompts.agent_hook import (
    CONTEXT_BLOCK_CLOSE,
    CONTEXT_BLOCK_OPEN,
    CONTEXT_EMPTY_TEMPLATE,
    CONTEXT_ERROR_TEMPLATE,
    CONTEXT_FOOTER,
    CONTEXT_HEADER_TEMPLATE,
    CONTEXT_RESULTS_INTRO,
    STOP_UPDATE_REASON,
)
from prompts.installer import HOOK_SCRIPT_TEMPLATE, HOOKS_README_TEMPLATE

__all__ = [
    "CONTEXT_BLOCK_CLOSE",
    "CONTEXT_BLOCK_OPEN",
    "CONTEXT_EMPTY_TEMPLATE",
    "CONTEXT_ERROR_TEMPLATE",
    "CONTEXT_FOOTER",
    "CONTEXT_HEADER_TEMPLATE",
    "CONTEXT_RESULTS_INTRO",
    "STOP_UPDATE_REASON",
    "HOOK_SCRIPT_TEMPLATE",
    "HOOKS_README_TEMPLATE",
]
