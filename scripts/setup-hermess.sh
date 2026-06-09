#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
SERVER_NAME="${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}"
SERVER_URL="${LLM_WIKI_MCP_URL:-http://127.0.0.1:${KB_PORT:-9999}${KB_MCP_PATH:-/mcp}}"
HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"

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
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_SOURCE="${REPO_ROOT}/skills/llm-wiki"
SKILL_DEST="${HERMES_HOME}/skills/llm-wiki"

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

echo "Installed Hermes/Hermess skill: ${SKILL_DEST}"

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes CLI not found. Add this block manually to ~/.hermes/config.yaml:" >&2
  sed 's/^/  /' "${REPO_ROOT}/mcp/hermess.yaml" >&2
  exit 0
fi

if [[ "${DRY_RUN}" == true ]]; then
  echo "[dry-run] hermes mcp remove ${SERVER_NAME} || true"
  echo "[dry-run] hermes mcp add ${SERVER_NAME} --url ${SERVER_URL}"
  echo "[dry-run] hermes mcp test ${SERVER_NAME}"
  exit 0
fi

hermes mcp remove "${SERVER_NAME}" >/dev/null 2>&1 || true
hermes mcp add "${SERVER_NAME}" --url "${SERVER_URL}"
hermes mcp test "${SERVER_NAME}" || true

echo "Hermes/Hermess MCP server '${SERVER_NAME}' points to ${SERVER_URL}. Restart Hermes or /reload-mcp if needed."
