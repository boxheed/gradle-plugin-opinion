# Instructions for AI Coding Agents (Jules)

Welcome to `gradle-plugin-opinion`. This document outlines the project conventions, branching strategy, and verification steps that all autonomous agents (such as Google Jules) must follow.

---

## 1. Branching Strategy & Target Branch

> [!IMPORTANT]
> **All Pull Requests MUST target the branch specified in the task / issue description (defaulting to `develop` if unspecified).**
> Never open Pull Requests against `master`.

- **Target / Base Branch:** Follow the branch specified in the issue/task (e.g. `- **Target Branch:** <branch>`). Defaults to `develop`.
- **Branch-Specific Remediations:** When remediating a vulnerability on a branch (such as a Dependabot PR branch `dependabot/...` or feature branch), checkout that branch, apply the fix, and submit the Pull Request targeting that specific branch.
- **Master Branch:** Reserved exclusively for releases and automated versioning. Never target `master`.

---

## 2. Dependency & Vulnerability Remediation

When remediating vulnerabilities detected by OSV Scanner or security issues:

1. **Direct Dependencies:**
   - Upgrade the dependency version in `buildscript { dependencies { ... } }` or `dependencies { ... }` in [`build.gradle`](file:///workspace/gradle-plugin-opinion/build.gradle).
2. **Transitive Dependencies:**
   - Enforce fixed versions using Gradle dependency constraints within the `dependencies { constraints { ... } }` block in [`build.gradle`](file:///workspace/gradle-plugin-opinion/build.gradle):

     ```groovy
     implementation('<group>:<artifact>') {
         because '<reason / CVE / GHSA-id>'
         version {
             require '<fixed-version>'
         }
     }
     ```
3. **Commit Formatting:**
   - Follow Conventional Commits: `fix(deps): remediate <VULNERABILITY_ID>`
4. **Issue Closing:**
   - Link and close the tracking issue in your Pull Request description: `Fixes #<issue-number>`

---

## 3. Verification & Build Commands

Before submitting a Pull Request, verify the changes locally:

```bash
# 1. Update/check OSV vulnerability lock and scanner
./gradlew osvInstall osvLockAndScan

# 2. Apply code style formatting
./gradlew spotlessApply

# 3. Run unit and integration tests
./gradlew test
```

All verification commands require Java 17.
