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

# Configure git identity for Aider if not already set
if ! git config user.name >/dev/null 2>&1; then
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
fi

echo "Running Aider remediation with model: ${MODEL}..."

AIDER_PROMPT=$(cat << 'EOF'
Remediate the OSV vulnerabilities reported in the OSV report.
Follow these strict rules from SKILL.md and AGENTS.md:
1. ONLY modify build.gradle. Do NOT create or modify osv-scanner.toml or any other file.
2. Direct Dependencies: If the vulnerable package is declared directly in build.gradle (e.g. in dependencies { ... } or buildscript { dependencies { ... } }), upgrade its version number in place.
3. Transitive Dependencies: If the package is brought in transitively (NOT declared directly in build.gradle), add a dependency constraint inside the existing project-level dependencies { constraints { ... } } block at the bottom of build.gradle.
4. Context & Syntax: NEVER place implementation(...) or constraints inside the buildscript { ... } block (buildscript only accepts classpath). All dependency constraints MUST be inside the project dependencies { constraints { ... } } block.
5. Verification: Ensure the test command succeeds cleanly without errors.
EOF
)

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
  --no-gitignore \
  --yes-always \
  --message "${AIDER_PROMPT}"

echo "Verifying remediation outcome..."
if ! ./gradlew osvInstall osvLockAndScan && ./gradlew spotlessCheck test; then
  echo "::error::Remediation did not produce a passing build. Discarding invalid edits."
  git checkout -- .
  exit 1
fi

echo "Remediation verified successfully."
