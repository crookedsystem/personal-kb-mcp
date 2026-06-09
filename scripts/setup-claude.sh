#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
SERVER_NAME="${LLM_WIKI_MCP_SERVER_NAME:-llm-wiki}"
SERVER_URL="${LLM_WIKI_MCP_URL:-http://127.0.0.1:${KB_PORT:-9999}${KB_MCP_PATH:-/mcp}}"
CLAUDE_MCP_SCOPE="${CLAUDE_MCP_SCOPE:-user}"
CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-${HOME}/.claude/skills}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --server-url)
      SERVER_URL="$2"
      shift 2
      ;;
    --server-name)
      SERVER_NAME="$2"
      shift 2
      ;;
    --scope)
      CLAUDE_MCP_SCOPE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_SOURCE="${REPO_ROOT}/skills/llm-wiki"
SKILL_DEST="${CLAUDE_SKILLS_DIR}/llm-wiki"

run() {
  if [[ "${DRY_RUN}" == true ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

if [[ ! -d "${SKILL_SOURCE}" ]]; then
  echo "Skill source not found: ${SKILL_SOURCE}" >&2
  exit 1
fi

run mkdir -p "${SKILL_DEST}"
run cp -R "${SKILL_SOURCE}/." "${SKILL_DEST}/"

echo "Installed Claude skill: ${SKILL_DEST}"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI not found. Copy mcp/claude.json into a project .mcp.json or pass it with --mcp-config." >&2
  exit 0
fi

if [[ "${DRY_RUN}" == true ]]; then
  echo "[dry-run] claude mcp remove -s ${CLAUDE_MCP_SCOPE} ${SERVER_NAME} || true"
  echo "[dry-run] claude mcp add -s ${CLAUDE_MCP_SCOPE} --transport http ${SERVER_NAME} ${SERVER_URL}"
  echo "[dry-run] claude mcp get ${SERVER_NAME}"
  exit 0
fi

claude mcp remove -s "${CLAUDE_MCP_SCOPE}" "${SERVER_NAME}" >/dev/null 2>&1 || true
claude mcp add -s "${CLAUDE_MCP_SCOPE}" --transport http "${SERVER_NAME}" "${SERVER_URL}"
claude mcp get "${SERVER_NAME}" || true

echo "Claude MCP server '${SERVER_NAME}' points to ${SERVER_URL}. Restart Claude Code if needed."
