#!/usr/bin/env bash
set -euo pipefail

MODEL="${AGY_MODEL:-gemini-3.8-flash}"
EFFORT="${AGY_EFFORT:-medium}"
REPORT="${1:-${OSV_REPORT_PATH:-build/osv-scanner/osv-scanner-scan.json}}"

# Ensure Antigravity CLI is installed
if ! command -v agy >/dev/null 2>&1; then
  echo "Antigravity CLI (agy) not found. Installing..."
  curl -fsSL https://antigravity.google/cli/install.sh | bash
  export PATH="${HOME}/.local/bin:${PATH}"
fi

# Configure permissions: allow gradle and file editing, deny direct git/gh actions
mkdir -p "${HOME}/.gemini/antigravity-cli"

PROVIDER_CONFIG=""
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  PROVIDER_CONFIG='"modelProvider": "gemini",'
fi

cat << EOF > "${HOME}/.gemini/antigravity-cli/settings.json"
{
  ${PROVIDER_CONFIG}
  "model": "${MODEL}",
  "agentMode": "accept-edits",
  "permissions": {
    "allow": [
      "command(./gradlew)",
      "write_file",
      "edit_file"
    ],
    "deny": [
      "command(git commit)",
      "command(git push)",
      "command(git checkout)",
      "command(gh)"
    ]
  }
}
EOF

echo "Running Antigravity CLI remediation with model: ${MODEL}..."
agy --model "${MODEL}" --effort "${EFFORT}" --output-format stream-json --print "Remediate OSV vulnerabilities in ${REPORT}" | \
  jq --unbuffered -r '
    select(.event == "step_update") |
    if .step_update.step_type == "tool" and .step_update.state == "ACTIVE" then
      "\n==> [\(.step_update.tool_name)] \(.step_update.tool_info.parameters.CommandLine // .step_update.tool_info.parameters.Path // "")"
    elif .step_update.step_type == "agent_response" and .step_update.text_delta then
      .step_update.text_delta
    else
      empty
    end
  '
