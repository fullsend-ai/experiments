#!/usr/bin/env python3
"""
Save review findings to SQLite cache.

Used in post-review.sh after agent completes.

Usage:
    python3 save.py --findings agent-result.json --pr 123 --sha abc123
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path
from store import ReviewMemoryStore, Finding


def extract_enrichment(file_path: str, line: int) -> tuple[str, str]:
    """
    Extract function name and code snippet using bash script.

    Returns: (function_name, code_snippet)
    """
    script_dir = Path(__file__).parent
    extract_script = script_dir / "extract_functions.sh"

    try:
        # Source the script and call functions
        bash_cmd = f"""
        source {extract_script}
        extract_function_name "{file_path}" {line}
        """
        result = subprocess.run(
            ["bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            check=True
        )
        function_name = result.stdout.strip() or "package"

        bash_cmd = f"""
        source {extract_script}
        extract_code_snippet "{file_path}" {line}
        """
        result = subprocess.run(
            ["bash", "-c", bash_cmd],
            capture_output=True,
            text=True,
            check=True
        )
        code_snippet = result.stdout.strip()

        return function_name, code_snippet

    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to extract for {file_path}:{line}: {e}", file=sys.stderr)
        return "package", ""


def save_findings(findings_file: str, pr_number: int, head_sha: str, db_path: str = ".fullsend/review-memory.db"):
    """
    Save findings to SQLite, enriching with function names and code snippets.

    Args:
        findings_file: Path to agent-result.json
        pr_number: PR number
        head_sha: Current commit SHA
        db_path: Database path
    """
    # Read findings
    with open(findings_file, 'r') as f:
        data = json.load(f)

    findings_data = data.get('findings', [])

    if not findings_data:
        print("No findings to save")
        return

    # Process each finding
    enriched_findings = []

    for f_data in findings_data:
        # Extract enrichment
        file_path = f_data.get('file', '')
        line = f_data.get('line', 0)

        function_name, code_snippet = extract_enrichment(file_path, line)

        # Create Finding object
        finding = Finding(
            file_path=file_path,
            function_name=function_name,
            category=f_data.get('category', 'unknown'),
            severity=f_data.get('severity', 'low'),
            description=f_data.get('description', ''),
            remediation=f_data.get('remediation', ''),
            code_snippet=code_snippet,
            line_number=line,
            pr_number=pr_number,
            first_seen_sha=head_sha,
            last_seen_sha=head_sha,
            status="new"
        )

        enriched_findings.append(finding)

    # Open store and save findings
    with ReviewMemoryStore(db_path) as store:
        # Deduplicate against prior findings
        result = store.deduplicate_findings(enriched_findings, pr_number)

        # Save all findings
        saved_count = 0
        for status_group in ['new', 'still_present', 'resolved']:
            for finding in result[status_group]:
                store.save_finding(finding)
                saved_count += 1

        print(f"✓ Saved {saved_count} finding(s)")
        print(f"  New: {len(result['new'])}")
        print(f"  Still present: {len(result['still_present'])}")
        print(f"  Resolved: {len(result['resolved'])}")


def main():
    parser = argparse.ArgumentParser(description="Save review findings to cache")
    parser.add_argument('--findings', required=True, help="Path to agent-result.json")
    parser.add_argument('--pr', type=int, required=True, help="PR number")
    parser.add_argument('--sha', required=True, help="Current HEAD SHA")
    parser.add_argument('--db', default=".fullsend/review-memory.db", help="Database path")

    args = parser.parse_args()

    # Ensure .fullsend directory exists
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)

    save_findings(args.findings, args.pr, args.sha, args.db)


if __name__ == "__main__":
    main()
