#!/usr/bin/env python3
"""
Parses OSV-Scanner JSON report and formats an actionable remediation prompt for Google Jules.
"""

import argparse
import json
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Prepare Jules remediation prompt from OSV scan report")
    parser.add_argument(
        "--report",
        default="build/osv-scanner/osv-scanner-scan.json",
        help="Path to osv-scanner-scan.json report"
    )
    parser.add_argument(
        "--target-branch",
        default="develop",
        help="Target branch for Jules remediation PR"
    )
    parser.add_argument(
        "--output",
        default="prompt.txt",
        help="File path to write the formatted prompt to"
    )
    return parser.parse_args()

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
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("")
        sys.exit(0)

    vulns_list_md = []
    for vuln_id, details in vulns_map.items():
        pkgs = ", ".join([f"`{p['name']}` ({p['version']})" for p in details["packages"]])
        vulns_list_md.append(f"- **Vulnerability ID:** [{vuln_id}](https://osv.dev/vulnerability/{vuln_id})\n  - **Summary:** {details['summary']}\n  - **Affected Package(s):** {pkgs}")

    vulns_formatted = "\n".join(vulns_list_md)
    vuln_ids_str = ", ".join(vulns_map.keys())

    prompt = f"""Remediate security vulnerabilities detected by OSV Scanner on branch `{args.target_branch}`.

### Detected Vulnerabilities:
{vulns_formatted}

### Instructions for Jules:
1. Base your work on the `{args.target_branch}` branch.
2. Review `build.gradle` and `osv-scanner.toml`.
3. If this is a direct dependency, upgrade its version in `buildscript.dependencies` or `dependencies`.
4. If it is a transitive dependency, add or update a constraint in the `constraints {{ ... }}` block in `build.gradle` (refer to existing patterns in `build.gradle`) to enforce a fixed, non-vulnerable version.
5. Verify the fix by running:
   ```bash
   ./gradlew osvInstall osvLockAndScan
   ./gradlew spotlessApply
   ./gradlew test
   ```
6. Use conventional commit formatting: `fix(deps): remediate {vuln_ids_str}`
7. Open a Pull Request targeting the `{args.target_branch}` branch.
"""

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"Generated remediation prompt for {len(vulns_map)} vulnerability/vulnerabilities:")
    print(prompt)

if __name__ == "__main__":
    main()
