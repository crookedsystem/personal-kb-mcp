#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
SERVER_NAME="${LLM_WIKI_MCP_SERVER_NAME:-llm_wiki}"
SERVER_URL="${LLM_WIKI_MCP_URL:-http://127.0.0.1:${KB_PORT:-9999}${KB_MCP_PATH:-/mcp}}"
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
CODEX_SKILLS_DIR="${CODEX_SKILLS_DIR:-${CODEX_HOME}/skills}"
CONFIG_PATH="${CODEX_CONFIG_PATH:-${CODEX_HOME}/config.toml}"

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
    --config)
      CONFIG_PATH="$2"
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
SKILL_DEST="${CODEX_SKILLS_DIR}/llm-wiki"

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

echo "Installed Codex skill: ${SKILL_DEST}"

if [[ "${DRY_RUN}" == true ]]; then
  echo "[dry-run] would update ${CONFIG_PATH} with [mcp_servers.${SERVER_NAME}] -> ${SERVER_URL}"
  exit 0
fi

mkdir -p "$(dirname "${CONFIG_PATH}")"
python3 - "${CONFIG_PATH}" "${SERVER_NAME}" "${SERVER_URL}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
server_name = sys.argv[2]
server_url = sys.argv[3]
marker_begin = "# llm-wiki setup: begin"
marker_end = "# llm-wiki setup: end"
server_key = json.dumps(server_name)
block = f"""{marker_begin}
[mcp_servers.{server_key}]
url = {json.dumps(server_url)}
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
{marker_end}
"""
existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
pattern = re.compile(r"^# llm-wiki setup: begin\n.*?^# llm-wiki setup: end\n?", re.M | re.S)
updated = pattern.sub("", existing).rstrip()
if updated:
    updated = f"{updated}\n\n{block}"
else:
    updated = block
config_path.write_text(updated, encoding="utf-8")
print(f"Updated {config_path}")
PY

echo "Codex MCP server '${SERVER_NAME}' points to ${SERVER_URL}. Restart Codex so it reloads config and skills."
