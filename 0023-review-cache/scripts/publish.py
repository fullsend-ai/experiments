#!/usr/bin/env python3
"""
Publication Policy Engine

Separates finding state from presentation strategy:
- State tracking: what findings exist (new/still_present/resolved/dismissed)
- Publication policy: how to present them (inline vs summary)

This solves the duplicate comment problem while maintaining visibility.

Usage:
    python3 publish.py \
      --findings classified-findings.json \
      --output github-comment.md
"""

import argparse
import json
from typing import Dict, List


class PublicationPolicy:
    """
    Determines HOW findings are presented based on state.

    Key insight: State tracking ≠ presentation strategy

    - new → inline comment (full details)
    - still_present → summary mention (no duplicate inline noise)
    - resolved → summary mention (show progress)
    - dismissed → summary mention (transparency)
    """

    def apply_policy(self, findings: List[dict]) -> Dict[str, List[dict]]:
        """
        Classify findings by publication strategy.

        Returns:
            {
                'inline_comments': [...],     # Post as inline GitHub comments
                'summary_resolved': [...],    # Mention in progress summary
                'summary_unresolved': [...],  # Mention in unresolved summary
                'summary_dismissed': [...]    # Mention in dismissed summary
            }
        """
        result = {
            'inline_comments': [],
            'summary_resolved': [],
            'summary_unresolved': [],
            'summary_dismissed': []
        }

        for finding in findings:
            status = finding.get('status', 'new')

            if status == 'new':
                # New findings: post full inline comment
                result['inline_comments'].append(finding)

            elif status == 'still_present':
                # Still present: mention in summary, don't post inline
                # This is the key to reducing duplicate noise
                result['summary_unresolved'].append(finding)

            elif status == 'resolved':
                # Resolved: show progress
                result['summary_resolved'].append(finding)

            elif status == 'dismissed':
                # Dismissed: show transparency (but don't post inline)
                result['summary_dismissed'].append(finding)

        return result


def severity_icon(severity: str) -> str:
    """Return emoji for severity level."""
    icons = {
        'critical': '🔴',
        'high': '🔴',
        'medium': '🟡',
        'low': '🟢',
        'info': 'ℹ️'
    }
    return icons.get(severity.lower(), '⚪')


def format_inline_comment(finding: dict) -> str:
    """
    Format a finding as an inline GitHub comment.

    Example:
        ### 🔴 race-condition in collector.go:221

        **Severity:** high

        Missing synchronization for `coldStart` variable access.

        **Remediation:**
        Add mutex protection or use atomic operations.
    """
    icon = severity_icon(finding.get('severity', 'medium'))
    category = finding.get('category', 'unknown')
    file_path = finding.get('file', 'unknown')
    line = finding.get('line', 0)
    function = finding.get('function', '')
    severity = finding.get('severity', 'medium')
    description = finding.get('description', '')
    remediation = finding.get('remediation', '')

    # Header
    location = f"{file_path}:{line}"
    if function and function != 'package':
        location += f" ({function})"

    comment = f"### {icon} {category} in {location}\n\n"
    comment += f"**Severity:** {severity}\n\n"
    comment += f"{description}\n"

    if remediation:
        comment += f"\n**Remediation:**\n{remediation}\n"

    return comment


def format_summary_item(finding: dict) -> str:
    """
    Format a finding as a summary line item.

    Example:
        - race-condition in collector.go:89 (coldStart)
    """
    category = finding.get('category', 'unknown')
    file_path = finding.get('file', 'unknown')
    line = finding.get('line', 0)
    function = finding.get('function', '')

    item = f"- {category} in {file_path}:{line}"
    if function and function != 'package':
        item += f" ({function})"

    # Add dismissal reason if present
    dismissal_reason = finding.get('dismissal_reason')
    if dismissal_reason:
        # Truncate long reasons
        reason = dismissal_reason[:60] + '...' if len(dismissal_reason) > 60 else dismissal_reason
        item += f"\n  *Reason: {reason}*"

    return item


def generate_github_comment(policy_result: Dict[str, List[dict]], verdict: str) -> str:
    """
    Generate the final GitHub comment.

    Structure:
    1. Inline comments for new findings (full details)
    2. Progress summary (resolved/unresolved/dismissed)
    """
    sections = []

    # Section 1: Inline comments for new findings
    inline = policy_result['inline_comments']
    if inline:
        sections.append("## Security Issues\n")
        for finding in inline:
            sections.append(format_inline_comment(finding))

    # Section 2: Progress summary
    resolved = policy_result['summary_resolved']
    unresolved = policy_result['summary_unresolved']
    dismissed = policy_result['summary_dismissed']

    if resolved or unresolved or dismissed:
        sections.append("\n---\n\n## Progress Summary\n")

        if resolved:
            sections.append(f"\n✅ **Resolved ({len(resolved)}):**\n")
            for finding in resolved:
                sections.append(format_summary_item(finding) + "\n")

        if unresolved:
            sections.append(f"\n⚠️ **Still Present ({len(unresolved)}):**\n")
            for finding in unresolved:
                sections.append(format_summary_item(finding) + "\n")

        if dismissed:
            sections.append(f"\nℹ️ **Dismissed ({len(dismissed)}):**\n")
            for finding in dismissed:
                sections.append(format_summary_item(finding) + "\n")

    # No findings at all
    if not inline and not resolved and not unresolved and not dismissed:
        sections.append("## ✅ No Issues Found\n\nAll checks passed!\n")

    return '\n'.join(sections)


def compute_resolved_findings(pr_number: int, db_path: str, current_findings: List[dict]) -> List[dict]:
    """
    Compute which findings from cache are now resolved (not in current output).
    """
    from pathlib import Path
    from store import ReviewMemoryStore

    if not Path(db_path).exists():
        return []

    # Build semantic keys for current findings
    current_keys = set()
    for f in current_findings:
        file_path = f.get('file', '')
        line = f.get('line', 0)
        category = f.get('category', 'unknown')
        function = f.get('function', 'package')
        line_bucket = (line // 10) * 10 if line else 0
        semantic_key = f"{file_path}:{function}:{category}:{line_bucket}"
        current_keys.add(semantic_key)

    # Query cache for prior findings
    resolved = []
    with ReviewMemoryStore(db_path) as store:
        prior_findings = store.get_pr_findings(pr_number)

        for prior in prior_findings:
            # Was in prior, not in current → resolved
            if prior.semantic_key not in current_keys:
                if prior.status in ['new', 'still_present']:
                    resolved.append({
                        'file': prior.file_path,
                        'line': prior.line_number,
                        'function': prior.function_name,
                        'category': prior.category,
                        'severity': prior.severity,
                        'status': 'resolved'
                    })

    return resolved


def main():
    parser = argparse.ArgumentParser(
        description="Apply publication policy to classified findings"
    )
    parser.add_argument('--findings', required=True,
                        help="Path to classified findings JSON")
    parser.add_argument('--output', required=True,
                        help="Path to output GitHub comment markdown")
    parser.add_argument('--pr', type=int,
                        help="PR number (optional, for computing resolved findings)")
    parser.add_argument('--db', default=".fullsend/review-memory.db",
                        help="Database path (optional, for computing resolved findings)")

    args = parser.parse_args()

    # Load classified findings
    with open(args.findings, 'r') as f:
        data = json.load(f)

    findings = data.get('findings', [])
    verdict = data.get('action', 'comment')

    # Apply publication policy
    policy = PublicationPolicy()
    policy_result = policy.apply_policy(findings)

    # Compute resolved findings if cache is available
    if args.pr:
        resolved_findings = compute_resolved_findings(args.pr, args.db, findings)
        policy_result['summary_resolved'] = resolved_findings

    # Print policy decisions
    print("Publication Policy Applied:")
    print(f"  Inline comments (new): {len(policy_result['inline_comments'])}")
    print(f"  Summary - Resolved: {len(policy_result['summary_resolved'])}")
    print(f"  Summary - Unresolved: {len(policy_result['summary_unresolved'])}")
    print(f"  Summary - Dismissed: {len(policy_result['summary_dismissed'])}")

    # Generate GitHub comment
    comment = generate_github_comment(policy_result, verdict)

    # Write output
    with open(args.output, 'w') as f:
        f.write(comment)

    print(f"\n✓ GitHub comment written to {args.output}")

    # Also write policy result as JSON for testing
    policy_json = args.output.replace('.md', '-policy.json')
    with open(policy_json, 'w') as f:
        json.dump(policy_result, f, indent=2)

    print(f"✓ Policy result written to {policy_json}")


if __name__ == "__main__":
    main()
