#!/usr/bin/env bash
set -euo pipefail

TARGET_BRANCH="${TARGET_BRANCH:-develop}"
VULN_IDS="${VULN_IDS:-OSV vulnerabilities}"
EVENT_NAME="${GITHUB_EVENT_NAME:-workflow_dispatch}"

if [[ -z "$(git status --porcelain)" ]]; then
  echo "::warning::Remediation agent finished without modifying any tracked files."
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "remediated=false" >> "$GITHUB_OUTPUT"
  fi
  exit 1
fi

echo "Verifying changes with Gradle..."
./gradlew osvInstall osvLockAndScan
./gradlew spotlessCheck test

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

COMMIT_MSG="fix(deps): remediate ${VULN_IDS}"

if [[ "${EVENT_NAME}" == "pull_request" ]]; then
  echo "Pushing remediation commit to PR branch ${TARGET_BRANCH}..."
  git add -A
  git commit -m "${COMMIT_MSG}"
  git push origin "HEAD:${TARGET_BRANCH}"
else
  REMEDIATE_BRANCH="fix/remediate-osv-${TARGET_BRANCH}"
  echo "Pushing remediation to branch ${REMEDIATE_BRANCH}..."
  git checkout -B "${REMEDIATE_BRANCH}"
  git add -A
  git commit -m "${COMMIT_MSG}"
  git push -f -u origin "${REMEDIATE_BRANCH}"

  EXISTING_PR=$(gh pr list --head "${REMEDIATE_BRANCH}" --base "${TARGET_BRANCH}" --json number --jq '.[0].number' 2>/dev/null || true)
  if [[ -z "${EXISTING_PR}" ]]; then
    echo "Creating new pull request..."
    gh pr create \
      --base "${TARGET_BRANCH}" \
      --head "${REMEDIATE_BRANCH}" \
      --title "${COMMIT_MSG}" \
      --body "Automated remediation generated for: ${VULN_IDS}"
  else
    echo "Updating existing pull request #${EXISTING_PR}..."
    gh pr edit "${EXISTING_PR}" \
      --title "${COMMIT_MSG}" \
      --body "Automated remediation updated for: ${VULN_IDS}"
  fi
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "remediated=true" >> "$GITHUB_OUTPUT"
fi
echo "Remediation successfully verified and published."
