#!/usr/bin/env bash
set -euo pipefail

MODEL="${AGY_MODEL:-gemini-3.5-flash-lite}"
EFFORT="${AGY_EFFORT:-low}"
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

echo "Running Antigravity CLI remediation with model: ${MODEL} (effort: ${EFFORT})..."
set +e
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
AGY_EXIT_CODE="${PIPESTATUS[0]}"
set -e

if [[ "${AGY_EXIT_CODE}" -ne 0 ]]; then
  echo "::error::Antigravity CLI remediation failed with exit code ${AGY_EXIT_CODE}. If the error was API_KEY_INVALID, verify that GEMINI_API_KEY in your repository secrets is a valid Gemini key from https://aistudio.google.com/app/apikey"
  exit "${AGY_EXIT_CODE}"
fi
