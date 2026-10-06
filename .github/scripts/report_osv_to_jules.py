#!/usr/bin/env python3
"""
Parses OSV-Scanner JSON report and files remediation issues for Google Jules via GitHub CLI (gh).
Includes deduplication against existing open issues.
"""

import argparse
import json
import os
import subprocess
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Report OSV scan vulnerabilities to Jules via GitHub Issues")
    parser.add_argument(
        "--report",
        default="build/osv-scanner/osv-scanner-scan.json",
        help="Path to osv-scanner-scan.json report"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print issues that would be created without creating them via gh"
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

def check_existing_issue(vuln_id):
    """Checks if an open issue already exists containing this vulnerability ID."""
    cmd = ["gh", "issue", "list", "--state", "open", "--search", vuln_id, "--json", "number,title"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        return issues[0] if issues else None
    except Exception as e:
        print(f"Warning: Failed to query existing issues via gh: {e}")
        return None

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

    title = f"Security: Remediate {vuln_id}"
    body = f"""### Vulnerability Detected

- **Vulnerability ID:** [{vuln_id}](https://osv.dev/vulnerability/{vuln_id})
- **Summary:** {summary}
- **Affected Package(s):**
{packages_md}
- **Target Branch:** `{target_branch}`

@jules Please remediate this vulnerability in the repository.

### Instructions for Jules:
1. Review `build.gradle` and `osv-scanner.toml`.
2. If this is a direct dependency, upgrade its version in `buildscript.dependencies` or `dependencies`.
3. If it is a transitive dependency, add or update a constraint in the `constraints {{ ... }}` block in `build.gradle` (refer to existing patterns in `build.gradle`) to enforce a fixed, non-vulnerable version.
4. Verify the fix by running:
   ```bash
   ./gradlew osvInstall osvLockAndScan
   ./gradlew spotlessApply
   ./gradlew test
   ```
5. Use conventional commit formatting: `fix(deps): remediate {vuln_id}`
6. Submit a Pull Request targeting the `{target_branch}` branch that references and closes this issue (`Fixes #<issue-id>`).
"""

    if dry_run:
        print(f"[DRY-RUN] Would create issue:\nTitle: {title}\nLabels: jules, security\nBody:\n{body}\n" + "-"*50)
        return True

    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--label", "jules,security",
        "--body", body
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Created issue for {vuln_id}: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating issue for {vuln_id}: {e.stderr}")
        return False

def main():
    args = parse_args()

    if not os.path.exists(args.report):
        print(f"Report file not found: {args.report}")
        sys.exit(0)

    try:
        with open(args.report, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read report JSON: {e}")
        sys.exit(1)

    # Collect vulnerabilities and their affected packages
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

    if not vulns_map:
        print("No vulnerabilities found in report.")
        sys.exit(0)

    print(f"Found {len(vulns_map)} unique vulnerability/vulnerabilities in scan report.")

    if not args.dry_run:
        ensure_labels()

    created_count = 0
    for vuln_id, details in vulns_map.items():
        if created_count >= args.max_issues:
            print(f"Reached maximum issue limit ({args.max_issues}). Deferring remaining vulnerabilities to next run.")
            break

        existing = check_existing_issue(vuln_id) if not args.dry_run else None
        if existing:
            print(f"Open issue already exists for {vuln_id}: #{existing.get('number')} - '{existing.get('title')}'. Skipping.")
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
