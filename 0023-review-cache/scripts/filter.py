#!/usr/bin/env python3
"""
Finding Classifier

Classifies findings by lifecycle state:
- new: First time seeing this finding
- still_present: Seen before, not fixed
- dismissed: Human decided it's not actionable
- resolved: Was present before, now fixed

Usage:
    python3 filter.py \\
      --findings agent-result.json \\
      --pr 123 \\
      --db .fullsend/review-memory.db \\
      --output classified-findings.json
"""

import argparse
import json
import sys
from pathlib import Path
from store import ReviewMemoryStore, Finding


def filter_findings(findings_file: str, pr_number: int, db_path: str, output_file: str):
    """
    Classify findings by lifecycle state.

    This is the classification layer:
    - CLASSIFY dismissed → add 'status': 'dismissed', 'dismissal_reason'
    - CLASSIFY still_present → add 'status': 'still_present', metadata
    - CLASSIFY new → add 'status': 'new'
    - PASS ALL findings to publish.py for presentation decisions

    Args:
        findings_file: Path to agent-result.json
        pr_number: PR number
        db_path: Database path
        output_file: Classified output path
    """
    # Read agent findings
    with open(findings_file, 'r') as f:
        data = json.load(f)

    agent_findings = data.get('findings', [])

    if not agent_findings:
        print("No findings to filter")
        # Write empty output
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        return

    # Open cache
    with ReviewMemoryStore(db_path) as store:
        classified = []
        dismissed_count = 0
        still_present_count = 0
        new_count = 0

        # Get prior findings for this PR
        prior_findings = store.get_pr_findings(pr_number)
        prior_map = {f.semantic_key: f for f in prior_findings}

        for f_data in agent_findings:
            # Build semantic key from finding
            file_path = f_data.get('file', '')
            line = f_data.get('line', 0)
            category = f_data.get('category', 'unknown')
            function_name = f_data.get('function', 'package')

            # Calculate semantic key (same logic as store.py)
            line_bucket = (line // 10) * 10 if line else 0
            semantic_key = f"{file_path}:{function_name}:{category}:{line_bucket}"

            # Check 1: Is this finding dismissed?
            dismissal_reason = store.get_dismissal_reason(semantic_key, pr_number)

            if dismissal_reason:
                # CLASSIFY as dismissed
                f_data['status'] = 'dismissed'
                f_data['dismissal_reason'] = dismissal_reason
                print(f"ℹ️  CLASSIFIED (dismissed): {category} in {file_path}:{function_name}")
                print(f"   Reason: {dismissal_reason}")
                dismissed_count += 1
                classified.append(f_data)
                continue

            # Check 2: Is this a still-present finding?
            if semantic_key in prior_map:
                prior = prior_map[semantic_key]

                # Was it previously reported?
                if prior.status in ['new', 'still_present']:
                    # CLASSIFY as still_present
                    f_data['status'] = 'still_present'
                    f_data['first_seen_sha'] = prior.first_seen_sha
                    print(f"📌 CLASSIFIED (still-present): {category} in {file_path}:{function_name}")
                    print(f"   First seen: {prior.first_seen_sha}")
                    still_present_count += 1
                    classified.append(f_data)
                    continue

            # Check 3: New finding
            f_data['status'] = 'new'
            print(f"🆕 CLASSIFIED (new): {category} in {file_path}:{function_name}")
            new_count += 1
            classified.append(f_data)

    # Update findings in result
    data['findings'] = classified

    # Write classified output
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Classification complete:")
    print(f"  Total input: {len(agent_findings)}")
    print(f"  New: {new_count}")
    print(f"  Still present: {still_present_count}")
    print(f"  Dismissed: {dismissed_count}")
    print(f"\n  All findings passed to publish.py for presentation policy")


def main():
    parser = argparse.ArgumentParser(description="Classify findings by lifecycle state")
    parser.add_argument('--findings', required=True, help="Path to agent-result.json")
    parser.add_argument('--pr', type=int, required=True, help="PR number")
    parser.add_argument('--db', default=".fullsend/review-memory.db", help="Database path")
    parser.add_argument('--output', required=True, help="Classified output path")

    args = parser.parse_args()

    # Check database exists
    if not Path(args.db).exists():
        print(f"No cache database found at {args.db} - marking all as 'new'", file=sys.stderr)
        # Mark all findings as 'new' since we have no prior context
        with open(args.findings, 'r') as f:
            data = json.load(f)
        for finding in data.get('findings', []):
            finding['status'] = 'new'
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        return

    filter_findings(args.findings, args.pr, args.db, args.output)


if __name__ == "__main__":
    main()
