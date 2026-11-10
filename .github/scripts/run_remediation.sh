#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AIDER_MODEL:-}" ]]; then
  if [[ -n "${OPENROUTER_API_KEY:-}" && -z "${GEMINI_API_KEY:-}" ]]; then
    MODEL="openrouter/google/gemini-2.5-flash-lite"
  else
    MODEL="gemini/gemini-2.5-flash-lite"
  fi
else
  MODEL="${AIDER_MODEL}"
fi
REPORT="${1:-${OSV_REPORT_PATH:-build/osv-scanner/osv-scanner-scan.json}}"

# Ensure uv and aider are available
if ! command -v aider >/dev/null 2>&1; then
  echo "Aider not found in PATH. Checking uv..."
  if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
  echo "Installing Aider via uv..."
  uv tool install --python 3.12 aider-chat
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "Running Aider remediation with model: ${MODEL}..."

aider \
  --model "${MODEL}" \
  --read .agents/skills/osv-remediation/SKILL.md \
  --read AGENTS.md \
  --read "${REPORT}" \
  --file build.gradle \
  --test-cmd "./gradlew osvInstall osvLockAndScan && ./gradlew spotlessCheck test" \
  --auto-test \
  --no-auto-commits \
  --no-dirty-commits \
  --yes-always \
  --message "Remediate the OSV vulnerabilities reported in ${REPORT}. Follow the guidelines in SKILL.md and AGENTS.md to add dependency constraints in build.gradle so that the test command succeeds."
