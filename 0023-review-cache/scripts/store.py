#!/usr/bin/env python3
"""
Core SQLite storage for review findings.

Used by save.py, load.py, and other scripts.
"""

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Finding:
    """A single review finding with lifecycle tracking."""

    # Identity
    file_path: str
    function_name: str
    category: str

    # Content
    severity: str
    description: str
    remediation: str = ""

    # Code context
    code_snippet: str = ""
    line_number: int = 0

    # Lifecycle
    pr_number: int = 0
    first_seen_sha: str = ""
    last_seen_sha: str = ""
    status: str = "new"  # new, still-present, resolved

    @property
    def semantic_key(self) -> str:
        """
        Enhanced semantic key: file:function:category:line_bucket

        Stable across refactoring, handles edge cases.
        """
        func = self.function_name or "package"
        line_bucket = (self.line_number // 10) * 10 if self.line_number else 0
        return f"{self.file_path}:{func}:{self.category}:{line_bucket}"

    @property
    def code_hash(self) -> str:
        """Hash actual code content, not metadata."""
        if self.code_snippet and self.code_snippet.strip():
            return hashlib.sha256(self.code_snippet.strip().encode()).hexdigest()[:16]
        else:
            # Fallback: use description
            return hashlib.sha256(self.description.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "semantic_key": self.semantic_key,
            "file": self.file_path,
            "function": self.function_name,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "remediation": self.remediation,
            "line": self.line_number,
            "code_snippet": self.code_snippet,
            "status": self.status,
            "first_seen_sha": self.first_seen_sha,
            "last_seen_sha": self.last_seen_sha,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        """Create Finding from dictionary."""
        return cls(
            file_path=data.get("file", ""),
            function_name=data.get("function", ""),
            category=data.get("category", ""),
            severity=data.get("severity", ""),
            description=data.get("description", ""),
            remediation=data.get("remediation", ""),
            code_snippet=data.get("code_snippet", ""),
            line_number=data.get("line", 0),
            pr_number=data.get("pr_number", 0),
            first_seen_sha=data.get("first_seen_sha", ""),
            last_seen_sha=data.get("last_seen_sha", ""),
            status=data.get("status", "new"),
        )


def sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize user input to prevent prompt injection.

    Removes command markers and limits length.
    """
    if not text:
        return ""

    # Remove prompt injection patterns
    dangerous_patterns = [
        r"IGNORE\s+ALL\s+PREVIOUS",
        r"IGNORE\s+INSTRUCTIONS",
        r"SYSTEM\s*:",
        r"<\|.*?\|>",  # ChatML markers
    ]

    sanitized = text
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    # HTML escape
    sanitized = sanitized.replace("<", "&lt;").replace(">", "&gt;")

    # Length limit
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... (truncated)"

    return sanitized.strip()


class ReviewMemoryStore:
    """SQLite storage for review findings with lifecycle tracking."""

    def __init__(self, db_path: str = ".fullsend/review-memory.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS findings (
                semantic_key TEXT PRIMARY KEY,
                pr_number INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                function_name TEXT NOT NULL,
                line_number INTEGER,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                remediation TEXT,
                code_snippet TEXT,
                code_hash TEXT,
                status TEXT NOT NULL,
                first_seen_sha TEXT NOT NULL,
                last_seen_sha TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pr ON findings(pr_number);
            CREATE INDEX IF NOT EXISTS idx_status ON findings(status);
            CREATE INDEX IF NOT EXISTS idx_file_func ON findings(file_path, function_name);

            -- PR-scoped dismissals for security
            CREATE TABLE IF NOT EXISTS intentional_exceptions (
                semantic_key TEXT,
                pr_number INTEGER NOT NULL,
                dismissal_reason TEXT NOT NULL,
                approved_by TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (semantic_key, pr_number),
                FOREIGN KEY (semantic_key) REFERENCES findings(semantic_key)
            );
        """)
        self.conn.commit()

    def save_finding(self, finding: Finding):
        """
        Save or update finding, preserving first_seen metadata.

        Uses explicit UPDATE vs INSERT to avoid overwriting history.
        """
        # Check if exists
        existing = self.conn.execute(
            "SELECT first_seen_sha, created_at FROM findings WHERE semantic_key = ?",
            (finding.semantic_key,),
        ).fetchone()

        now = datetime.now().isoformat()

        if existing:
            # Update: preserve first_seen and created_at
            self.conn.execute(
                """
                UPDATE findings
                SET last_seen_sha = ?,
                    status = ?,
                    line_number = ?,
                    description = ?,
                    remediation = ?,
                    code_snippet = ?,
                    code_hash = ?,
                    updated_at = ?
                WHERE semantic_key = ?
            """,
                (
                    finding.last_seen_sha,
                    finding.status,
                    finding.line_number,
                    sanitize_text(finding.description, max_length=1000),
                    sanitize_text(finding.remediation, max_length=1000),
                    finding.code_snippet,
                    finding.code_hash,
                    now,
                    finding.semantic_key,
                ),
            )
        else:
            # Insert new finding
            self.conn.execute(
                """
                INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    finding.semantic_key,
                    finding.pr_number,
                    finding.file_path,
                    finding.function_name,
                    finding.line_number,
                    finding.category,
                    finding.severity,
                    sanitize_text(finding.description, max_length=1000),
                    sanitize_text(finding.remediation, max_length=1000),
                    finding.code_snippet,
                    finding.code_hash,
                    finding.status,
                    finding.first_seen_sha,
                    finding.last_seen_sha,
                    now,  # created_at
                    now,  # updated_at
                ),
            )

        self.conn.commit()

    def get_pr_findings(self, pr_number: int) -> List[Finding]:
        """Get all findings for a PR."""
        cursor = self.conn.execute(
            """
            SELECT * FROM findings WHERE pr_number = ? ORDER BY severity DESC, file_path, line_number
        """,
            (pr_number,),
        )

        findings = []
        for row in cursor.fetchall():
            finding = Finding(
                file_path=row["file_path"],
                function_name=row["function_name"],
                category=row["category"],
                severity=row["severity"],
                description=row["description"],
                remediation=row["remediation"] or "",
                code_snippet=row["code_snippet"] or "",
                line_number=row["line_number"] or 0,
                pr_number=row["pr_number"],
                first_seen_sha=row["first_seen_sha"],
                last_seen_sha=row["last_seen_sha"],
                status=row["status"],
            )
            findings.append(finding)

        return findings

    def dismiss_finding(
        self, semantic_key: str, pr_number: int, reason: str, approved_by: str = "human"
    ):
        """
        Dismiss a finding with sanitized reasoning.

        PR-scoped for security.
        """
        sanitized_reason = sanitize_text(reason, max_length=500)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO intentional_exceptions VALUES (?, ?, ?, ?, ?)
        """,
            (
                semantic_key,
                pr_number,
                sanitized_reason,
                approved_by,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()

    def get_dismissal_reason(self, semantic_key: str, pr_number: int) -> Optional[str]:
        """Get dismissal reason for a finding (PR-scoped)."""
        cursor = self.conn.execute(
            """
            SELECT dismissal_reason FROM intentional_exceptions
            WHERE semantic_key = ? AND pr_number = ?
        """,
            (semantic_key, pr_number),
        )

        row = cursor.fetchone()
        return row["dismissal_reason"] if row else None

    def deduplicate_findings(self, new_findings: List[Finding], pr_number: int) -> dict:
        """
        Deduplicate new findings against prior findings for this PR.

        Returns:
            {
                'new': [...],
                'still_present': [...],
                'resolved': [...]
            }
        """
        result = {"new": [], "still_present": [], "resolved": []}

        # Get prior findings
        prior_findings = self.get_pr_findings(pr_number)
        prior_map = {f.semantic_key: f for f in prior_findings}

        seen_keys = set()

        # Process new findings
        for finding in new_findings:
            key = finding.semantic_key

            if key in prior_map:
                # Same finding from before
                finding.status = "still_present"
                finding.first_seen_sha = prior_map[key].first_seen_sha
                result["still_present"].append(finding)
                seen_keys.add(key)
            else:
                # New finding
                finding.status = "new"
                result["new"].append(finding)
                seen_keys.add(key)

        # Check for resolved findings
        for key, prior_finding in prior_map.items():
            if key not in seen_keys:
                prior_finding.status = "resolved"
                result["resolved"].append(prior_finding)

        return result

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
        return False  # Don't suppress exceptions


if __name__ == "__main__":
    # Simple test using context manager
    with ReviewMemoryStore(":memory:") as store:
        # Save a finding
        f = Finding(
            file_path="internal/auth.go",
            function_name="CheckPermission",
            category="auth-bypass",
            severity="high",
            description="Missing admin check",
            line_number=42,
            pr_number=123,
            first_seen_sha="abc123",
            last_seen_sha="abc123",
        )

        store.save_finding(f)
        print(f"✓ Saved finding: {f.semantic_key}")

        # Load findings
        findings = store.get_pr_findings(123)
        print(f"✓ Loaded {len(findings)} finding(s)")

        # Dismiss
        store.dismiss_finding(f.semantic_key, 123, "This is intentional")
        reason = store.get_dismissal_reason(f.semantic_key, 123)
        print(f"✓ Dismissal reason: {reason}")

    print("\n✅ store.py working correctly!")
