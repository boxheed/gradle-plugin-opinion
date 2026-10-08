#!/usr/bin/env python3
"""
Parses OSV-Scanner JSON report and manages remediation issues for Google Jules via GitHub CLI (gh).
- Deduplicates against existing open issues.
- Automatically closes open issues when vulnerabilities are resolved (directly or as side-effects).
- Directs Jules to remediate on the specific target branch.
"""

import argparse
import json
import os
import re
import subprocess
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Report and reconcile OSV scan vulnerabilities for Jules via GitHub Issues")
    parser.add_argument(
        "--report",
        default="build/osv-scanner/osv-scanner-scan.json",
        help="Path to osv-scanner-scan.json report"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions that would be taken without creating or closing issues via gh"
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=5,
        help="Maximum number of new issues to create per run (default: 5)"
    )
    parser.add_argument(
        "--target-branch",
        default="develop",
        help="Target branch for Jules remediation PRs (default: develop)"
    )
    return parser.parse_args()

def extract_issue_metadata(issue):
    """Extracts vulnerability ID and target branch from an issue."""
    body = issue.get("body", "")
    title = issue.get("title", "")

    vuln_id = None
    target_branch = None

    # 1. Extract from body:
    # - **Vulnerability ID:** [GHSA-xxx](...) or GHSA-xxx
    m_vuln = re.search(r"\*\*Vulnerability ID:\*\*\s*(?:\[([^\]]+)\]|([A-Za-z0-9_-]+))", body)
    if m_vuln:
        vuln_id = (m_vuln.group(1) or m_vuln.group(2)).strip()

    # - **Target Branch:** `develop` or develop
    m_branch = re.search(r"\*\*Target Branch:\*\*\s*(?:`([^`]+)`|([A-Za-z0-9_./-]+))", body)
    if m_branch:
        target_branch = (m_branch.group(1) or m_branch.group(2)).strip()

    # 2. Extract from title fallback:
    # Security: Remediate GHSA-xxx on <target_branch> OR Security: Remediate GHSA-xxx
    m_title = re.search(r"Security:\s*Remediate\s+([A-Za-z0-9_-]+)(?:\s+on\s+([A-Za-z0-9_./-]+))?", title)
    if m_title:
        if not vuln_id:
            vuln_id = m_title.group(1).strip()
        if not target_branch and m_title.group(2):
            target_branch = m_title.group(2).strip()

    return vuln_id, target_branch

def get_open_remediation_issues(target_branch):
    """Fetches all open security issues for the specified target branch."""
    cmd = [
        "gh", "issue", "list",
        "--state", "open",
        "--label", "security",
        "--limit", "100",
        "--json", "number,title,body"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        branch_issues = []
        for issue in issues:
            vuln_id, issue_branch = extract_issue_metadata(issue)
            # Default issue_branch to develop if unspecified in older issues
            if not issue_branch:
                issue_branch = "develop"
            if vuln_id and issue_branch == target_branch:
                branch_issues.append((issue, vuln_id))
        return branch_issues
    except Exception as e:
        print(f"Warning: Failed to query open issues via gh: {e}")
        return []

def reconcile_resolved_issues(open_issues, active_vuln_ids, target_branch, dry_run):
    """
    Closes open issues whose vulnerabilities are no longer present in the scan report.
    This handles cases where updating one dependency remediates multiple vulnerabilities.
    """
    closed_count = 0
    for issue, vuln_id in open_issues:
        if vuln_id not in active_vuln_ids:
            issue_num = issue["number"]
            comment = (
                f"Vulnerability `{vuln_id}` is no longer detected in OSV scan results on branch `{target_branch}`. "
                f"Closing issue as resolved (either remediated directly or as a side-effect of another dependency update)."
            )
            if dry_run:
                print(f"[DRY-RUN] Would close resolved issue #{issue_num} ({vuln_id}) on {target_branch}: {comment}")
            else:
                cmd = [
                    "gh", "issue", "close", str(issue_num),
                    "--comment", comment,
                    "--reason", "completed"
                ]
                try:
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                    print(f"Closed resolved issue #{issue_num} ({vuln_id}) on branch '{target_branch}'.")
                    closed_count += 1
                except subprocess.CalledProcessError as e:
                    print(f"Error closing issue #{issue_num}: {e.stderr}")
    return closed_count

def ensure_labels():
    """Ensures that required labels exist in the repository."""
    labels = [
        ("jules", "0E8A16", "Trigger Google Jules remediation agent"),
        ("security", "D93F0B", "Security vulnerabilities")
    ]
    for name, color, description in labels:
        try:
            subprocess.run(
                ["gh", "label", "create", name, "--color", color, "--description", description, "--force"],
                capture_output=True,
                text=True,
                check=False
            )
        except Exception:
            pass

def create_issue(vuln_id, summary, affected_packages, target_branch, dry_run):
    """Creates a GitHub issue with instructions for Jules."""
    packages_md = "\n".join([f"- `{pkg['name']}` (detected version: `{pkg['version']}`)" for pkg in affected_packages])

    title = f"Security: Remediate {vuln_id} on {target_branch}"
    body = f"""### Vulnerability Detected

- **Vulnerability ID:** [{vuln_id}](https://osv.dev/vulnerability/{vuln_id})
- **Summary:** {summary}
- **Affected Package(s):**
{packages_md}
- **Target Branch:** `{target_branch}`

@jules Please remediate this vulnerability on the branch `{target_branch}` in the repository.

### Instructions for Jules:
1. Base your work on the branch `{target_branch}`: checkout `{target_branch}` (e.g. `git fetch origin {target_branch} && git checkout {target_branch}`) before making changes.
2. Review `build.gradle` and `osv-scanner.toml`.
3. If this is a direct dependency, upgrade its version in `buildscript.dependencies` or `dependencies`.
4. If it is a transitive dependency, add or update a constraint in the `constraints {{ ... }}` block in `build.gradle` (refer to existing patterns in `build.gradle`) to enforce a fixed, non-vulnerable version.
5. Verify the fix by running:
   ```bash
   ./gradlew osvInstall osvLockAndScan
   ./gradlew spotlessApply
   ./gradlew test
   ```
6. Use conventional commit formatting: `fix(deps): remediate {vuln_id}`
7. Submit a Pull Request targeting the `{target_branch}` branch that references and closes this issue (`Fixes #<issue-id>`).
8. Include `Target Branch: {target_branch}` in the Pull Request description.
"""

    if dry_run:
        print(f"[DRY-RUN] Would create issue:\nTitle: {title}\nLabels: security -> then add jules\nBody:\n{body}\n" + "-"*50)
        return True

    # Step 1: Create issue with 'security' label first
    create_cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--label", "security",
        "--body", body
    ]
    try:
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        issue_ref = result.stdout.strip()
        print(f"Created issue for {vuln_id}: {issue_ref}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating issue for {vuln_id}: {e.stderr}")
        return False

    # Step 2: Apply 'jules' label separately so GitHub emits the 'issues.labeled' webhook event
    label_cmd = [
        "gh", "issue", "edit", issue_ref,
        "--add-label", "jules"
    ]
    try:
        subprocess.run(label_cmd, capture_output=True, text=True, check=True)
        print(f"Added 'jules' label to issue {issue_ref} to trigger Jules remediation agent.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error adding 'jules' label to issue {issue_ref}: {e.stderr}")
        return False

def main():
    args = parse_args()

    # Prevent recursive runs on Jules's own remediation PRs/branches
    if args.target_branch.startswith("fix/remediate-") or args.target_branch.startswith("jules/"):
        print(f"Skipping issue creation on Jules remediation branch: {args.target_branch}")
        sys.exit(0)

    if not os.path.exists(args.report):
        print(f"Report file not found: {args.report}")
        sys.exit(0)

    try:
        with open(args.report, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read report JSON: {e}")
        sys.exit(1)

    # Collect currently active vulnerabilities and their affected packages
    vulns_map = {}
    for res in data.get("results", []):
        for pkg_entry in res.get("packages", []):
            pkg_info = pkg_entry.get("package", {})
            pkg_name = pkg_info.get("name", "unknown")
            pkg_version = pkg_info.get("version", "unknown")
            for vuln in pkg_entry.get("vulnerabilities", []):
                vuln_id = vuln.get("id")
                if not vuln_id:
                    continue
                if vuln_id not in vulns_map:
                    vulns_map[vuln_id] = {
                        "summary": vuln.get("summary") or "No summary provided",
                        "packages": []
                    }
                vulns_map[vuln_id]["packages"].append({
                    "name": pkg_name,
                    "version": pkg_version
                })

    active_vuln_ids = set(vulns_map.keys())

    if not args.dry_run:
        ensure_labels()

    # Fetch open issues for this target branch
    open_issues = get_open_remediation_issues(args.target_branch) if not args.dry_run else []

    # Reconcile: Close open issues whose vulnerabilities are no longer present in the report
    closed_count = reconcile_resolved_issues(open_issues, active_vuln_ids, args.target_branch, args.dry_run)
    if closed_count > 0:
        print(f"Reconciled and closed {closed_count} resolved issue(s) on branch '{args.target_branch}'.")

    # If no active vulnerabilities remain, exit cleanly
    if not vulns_map:
        print("No active vulnerabilities found in report. All clear!")
        sys.exit(0)

    print(f"Found {len(vulns_map)} active vulnerability/vulnerabilities in scan report.")

    # Determine which vulnerabilities already have an active open issue
    already_open_vuln_ids = {vuln_id for issue, vuln_id in open_issues if vuln_id in active_vuln_ids}

    created_count = 0
    for vuln_id, details in vulns_map.items():
        if created_count >= args.max_issues:
            print(f"Reached maximum issue limit ({args.max_issues}). Deferring remaining vulnerabilities to next run.")
            break

        if vuln_id in already_open_vuln_ids:
            print(f"Open issue already exists for {vuln_id} on {args.target_branch}. Skipping.")
            continue

        success = create_issue(
            vuln_id=vuln_id,
            summary=details["summary"],
            affected_packages=details["packages"],
            target_branch=args.target_branch,
            dry_run=args.dry_run
        )
        if success:
            created_count += 1

    # Exit with code 1 so CI marks the scan as failed when vulnerabilities exist
    sys.exit(1)

if __name__ == "__main__":
    main()
