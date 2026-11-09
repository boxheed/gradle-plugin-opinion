---
name: osv-remediation
description: >-
  Use this skill to investigate and remediate security vulnerabilities detected by OSV Scanner in this Gradle project.
---

# OSV Vulnerability Remediation

This skill guides the automated remediation of security vulnerabilities reported by OSV Scanner in this repository.

## Workflow

### 1. Identify Vulnerabilities
Read the OSV Scanner report at `build/osv-scanner/osv-scanner-scan.json` (or generate it by running `./gradlew osvInstall osvLockAndScan`).

For each vulnerability entry:
- Note the **Vulnerability ID** (e.g. `GHSA-xxx` or `CVE-xxx`).
- Note the **Package Name** and **Current Version** from `packages[].package`.
- Inspect `vulnerabilities[].affected[].ranges[].events` for the minimum `fixed` version that resolves the advisory.

### 2. Apply Remediation in `build.gradle`
Inspect `build.gradle` (and `osv-scanner.toml` if applicable):

- **Direct Dependencies:**
  If the affected package is declared directly in `buildscript.dependencies` or `dependencies`, update its version to the fixed version.

- **Transitive Dependencies:**
  If the package is a transitive dependency brought in by a plugin or library, enforce the fixed version using a Gradle dependency constraint within the `dependencies { constraints { ... } }` block in `build.gradle`:

  ```groovy
  implementation('<group>:<artifact>') {
      because '<reason / CVE / GHSA-id>'
      version {
          require '<fixed-version>'
      }
  }
  ```

### 3. Handle Breaking Changes
If bumping a dependency introduces compilation or API incompatibilities in the project, update the affected source or test files to restore compatibility while keeping the patched dependency version.

### 4. Verification & Formatting
Run the verification commands in sequence to ensure the fix is clean, properly formatted, and passes all tests:

```bash
# 1. Update OSV lockfile and verify no vulnerabilities remain
./gradlew osvInstall osvLockAndScan

# 2. Apply code style formatting
./gradlew spotlessApply

# 3. Execute test suite
./gradlew test
```

### 5. Execution Boundaries
- **CI Mode:** When invoked in CI, leave all modified files in the working directory. Do NOT execute `git commit`, `git checkout -b`, `git push`, or `gh pr create`; the CI runner handles commits, branches, and PR creation.
- **Local Developer Mode:** When invoked locally by a developer, summarize the changes and patched versions cleanly.
