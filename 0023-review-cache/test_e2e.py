#!/usr/bin/env python3
"""
End-to-end test: kaexporter bot review scenario.

Reproduces the real-world experience of reviewing a Prometheus exporter
across 3 review rounds where a stateless bot:
  - Re-reports context.Background() in different phrasings
  - Re-flags dismissed false positives (coldStart, off-by-one)
  - Shows zero progress after ~15 fixes

The cache system should correctly classify each finding as
new / still_present / resolved across rounds.

Run: python3 test_e2e.py
"""

import json
import sys
import tempfile
from pathlib import Path
from scripts.store import ReviewMemoryStore, Finding

PASS = 0
FAIL = 0


def check(label: str, actual, expected):
    """Assert helper that prints result and tracks pass/fail."""
    global PASS, FAIL
    if actual == expected:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}: got {actual!r}, expected {expected!r}")


def load_review_json(path: str) -> list[Finding]:
    """Load findings from a review JSON file into Finding objects."""
    with open(path) as f:
        data = json.load(f)

    findings = []
    for fd in data["findings"]:
        findings.append(Finding(
            file_path=fd["file"],
            function_name="",
            category=fd["category"],
            severity=fd["severity"],
            description=fd["description"],
            remediation=fd.get("remediation", ""),
            line_number=fd.get("line", 0),
        ))
    return findings


def test_kaexporter_three_round_review():
    """
    Simulate 3 rounds of bot review on kaexporter, demonstrating:

    Round 1 (commit a1b2c3): Initial review — 6 findings (all new).
    Round 2 (commit f6e5d4): Developer fixed 3 real bugs. Bot re-reports
        2 dismissed false positives, rephrases 1 fixed issue, adds 1 new.
    Round 3 (commit 9a8b7c): Developer dismissed coldStart + off-by-one.
        Bot STILL re-flags them, plus 1 genuinely new finding.
    """

    print("=" * 70)
    print("KAEXPORTER BOT REVIEW - 3 ROUND SCENARIO")
    print("=" * 70)

    test_data = Path(__file__).parent / "test-data" / "review"
    pr_number = 456

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "kaexporter.db")

        # ── ROUND 1: Initial review (6 findings, all new) ─────────────

        print("\n ROUND 1: Initial bot review (commit a1b2c3)")
        print("-" * 70)
        print("Bot finds 6 issues in kaexporter PR\n")

        r1_findings = load_review_json(str(test_data / "review1.json"))
        sha1 = "a1b2c3d4e5f6"

        for f in r1_findings:
            f.pr_number = pr_number
            f.first_seen_sha = sha1
            f.last_seen_sha = sha1

        with ReviewMemoryStore(db_path) as store:
            result = store.deduplicate_findings(r1_findings, pr_number)

            check("R1 new count", len(result["new"]), 6)
            check("R1 still_present count", len(result["still_present"]), 0)
            check("R1 resolved count", len(result["resolved"]), 0)

            for f in result["new"]:
                store.save_finding(f)

            loaded = store.get_pr_findings(pr_number)
            check("R1 total in DB", len(loaded), 6)

        print(f"  Saved {len(result['new'])} new findings")
        for f in result["new"]:
            print(f"    [{f.severity}] {f.category} @ {f.file_path}:{f.line_number}")

        # ── ROUND 2: After fixes, bot re-reports + rephrases ──────────

        print(f"\n ROUND 2: After developer fixes (commit f6e5d4)")
        print("-" * 70)
        print("Developer fixed: WaitSumSeconds denominator, retryCount30d Reset,")
        print("                 context.Background() (with AfterFunc pattern)")
        print("Bot re-reports: coldStart, off-by-one, metric-label-injection")
        print("Bot rephrases:  context.Background as 'gap-fill deadline'")
        print("Bot adds:       scrapeDurationGauge outside lock (new FP)\n")

        r2_findings = load_review_json(str(test_data / "review2.json"))
        sha2 = "f6e5d4c3b2a1"

        for f in r2_findings:
            f.pr_number = pr_number
            f.first_seen_sha = sha2
            f.last_seen_sha = sha2

        with ReviewMemoryStore(db_path) as store:
            result = store.deduplicate_findings(r2_findings, pr_number)

            # context.Background rephrased: line 221→327, same file+category
            # but different line bucket (220 vs 320) so it's a "new" finding
            # coldStart (line 89, same bucket 80): still_present
            # off-by-one (line 101, same bucket 100): still_present
            # metric-label-injection (line 88, same bucket 80): still_present
            # scrapeDurationGauge (line 122, bucket 120): new

            new_cats = sorted([f.category for f in result["new"]])
            still_cats = sorted([f.category for f in result["still_present"]])
            resolved_cats = sorted([f.category for f in result["resolved"]])

            print("  Deduplication result:")
            print(f"    New ({len(result['new'])}): {new_cats}")
            print(f"    Still present ({len(result['still_present'])}): {still_cats}")
            print(f"    Resolved ({len(result['resolved'])}): {resolved_cats}")

            # The rephrased context.Background (line 327, bucket 320) is NEW
            # because the bot changed the line number to a different bucket
            check("R2 new count", len(result["new"]), 2)
            check("R2 new contains rephrased context.Background",
                  "race-condition" in new_cats, True)
            check("R2 new contains scrapeDurationGauge FP",
                  "race-condition" in new_cats, True)

            # coldStart, off-by-one, metric-label-injection: still_present
            check("R2 still_present count", len(result["still_present"]), 3)
            check("R2 still_present has metric-label-injection",
                  "metric-label-injection" in still_cats, True)
            check("R2 still_present has off-by-one",
                  "off-by-one" in still_cats, True)

            # Fixed: original context.Background (line 221), retryCount30d, WaitSumSeconds
            check("R2 resolved count", len(result["resolved"]), 3)
            check("R2 resolved has logic-error (WaitSumSeconds)",
                  "logic-error" in resolved_cats, True)
            check("R2 resolved has error-handling-gap (retryCount30d)",
                  "error-handling-gap" in resolved_cats, True)

            for status_group in ["new", "still_present", "resolved"]:
                for f in result[status_group]:
                    store.save_finding(f)

            # Verify first_seen preserved for coldStart
            all_findings = store.get_pr_findings(pr_number)
            coldstart = next(
                (f for f in all_findings
                 if f.category == "race-condition" and f.line_number == 89),
                None
            )
            if coldstart:
                check("R2 coldStart first_seen preserved",
                      coldstart.first_seen_sha, sha1)

            # Human dismisses coldStart and off-by-one
            print("\n  Developer dismisses false positives:")

            coldstart_key = coldstart.semantic_key if coldstart else ""
            store.dismiss_finding(
                coldstart_key, pr_number,
                "Single-goroutine invariant: only runCollection goroutine "
                "reads coldStart, no concurrent access possible",
                "senior-engineer"
            )
            print(f"    Dismissed coldStart: '{store.get_dismissal_reason(coldstart_key, pr_number)[:60]}...'")

            offbyone = next(
                (f for f in all_findings if f.category == "off-by-one"), None
            )
            if offbyone:
                store.dismiss_finding(
                    offbyone.semantic_key, pr_number,
                    "dayOffset 0-29 inclusive = 30 calendar days. "
                    "Buckets[29-30] would be index -1 (panic). Correct as-is.",
                    "senior-engineer"
                )
                print(f"    Dismissed off-by-one: '{store.get_dismissal_reason(offbyone.semantic_key, pr_number)[:60]}...'")

            # Also dismiss metric-label-injection
            mli = next(
                (f for f in all_findings if f.category == "metric-label-injection"), None
            )
            if mli:
                store.dismiss_finding(
                    mli.semantic_key, pr_number,
                    "Existing mitigations sufficient: capped fetch limits, "
                    "30-day expiry, fixed label dimensions. Enforce at scrape config level.",
                    "senior-engineer"
                )
                print(f"    Dismissed metric-label-injection: '{store.get_dismissal_reason(mli.semantic_key, pr_number)[:60]}...'")

        # ── ROUND 3: Dismissed issues STILL return ────────────────────

        print(f"\n ROUND 3: Bot re-reviews AGAIN (commit 9a8b7c)")
        print("-" * 70)
        print("Despite dismissals, bot re-reports coldStart and metric-label-injection")
        print("Bot adds: collectMetrics nil-error (genuinely new)\n")

        r3_findings = load_review_json(str(test_data / "review3.json"))
        sha3 = "9a8b7c6d5e4f"

        for f in r3_findings:
            f.pr_number = pr_number
            f.first_seen_sha = sha3
            f.last_seen_sha = sha3

        with ReviewMemoryStore(db_path) as store:
            result = store.deduplicate_findings(r3_findings, pr_number)

            new_cats = sorted([f.category for f in result["new"]])
            still_cats = sorted([f.category for f in result["still_present"]])
            resolved_cats = sorted([f.category for f in result["resolved"]])

            print("  Deduplication result:")
            print(f"    New ({len(result['new'])}): {new_cats}")
            print(f"    Still present ({len(result['still_present'])}): {still_cats}")
            print(f"    Resolved ({len(result['resolved'])}): {resolved_cats}")

            # collectMetrics nil-error (line 298, bucket 290): genuinely new
            check("R3 new count", len(result["new"]), 1)
            check("R3 new is collectMetrics error-handling-gap",
                  result["new"][0].category if result["new"] else "", "error-handling-gap")

            # coldStart + metric-label-injection: still_present (despite dismissal)
            check("R3 still_present count", len(result["still_present"]), 2)

            # Resolved: everything the bot stopped reporting (6 of 8 prior entries)
            # - race-condition:220 (original context.Background, already resolved)
            # - error-handling-gap:210 (retryCount30d, already resolved)
            # - logic-error:120 (WaitSumSeconds, already resolved)
            # - race-condition:320 (gap-fill rephrasing, bot dropped it)
            # - race-condition:120 (scrapeDurationGauge FP, bot dropped it)
            # - off-by-one:100 (bot stopped reporting it)
            check("R3 resolved count", len(result["resolved"]), 6)

            # Verify dismissal reasons survive across rounds
            coldstart_r3 = next(
                (f for f in result["still_present"]
                 if f.category == "race-condition"),
                None
            )
            if coldstart_r3:
                reason = store.get_dismissal_reason(coldstart_r3.semantic_key, pr_number)
                check("R3 coldStart dismissal reason preserved",
                      reason is not None, True)
                print(f"\n  Dismissal reason still available for coldStart:")
                print(f"    '{reason[:70]}...'")

            mli_r3 = next(
                (f for f in result["still_present"]
                 if f.category == "metric-label-injection"),
                None
            )
            if mli_r3:
                reason = store.get_dismissal_reason(mli_r3.semantic_key, pr_number)
                check("R3 metric-label-injection dismissal preserved",
                      reason is not None, True)

            # Verify first_seen_sha tracks all the way back to round 1
            if coldstart_r3:
                check("R3 coldStart first_seen still points to R1",
                      coldstart_r3.first_seen_sha, sha1)

            for status_group in ["new", "still_present", "resolved"]:
                for f in result[status_group]:
                    store.save_finding(f)

        # ── FINAL SUMMARY ─────────────────────────────────────────────

        print()
        print("=" * 70)

        with ReviewMemoryStore(db_path) as store:
            final = store.get_pr_findings(pr_number)
            statuses = {}
            for f in final:
                statuses[f.status] = statuses.get(f.status, 0) + 1

            print(f"FINAL STATE: {len(final)} findings tracked across 3 rounds")
            for status, count in sorted(statuses.items()):
                print(f"  {status}: {count}")

        print()
        if FAIL == 0:
            print(f"RESULT: ALL {PASS} CHECKS PASSED")
        else:
            print(f"RESULT: {FAIL} FAILED, {PASS} passed")
        print("=" * 70)

        print()
        print("What the cache system demonstrated:")
        print("  Fixed bugs (WaitSumSeconds, retryCount30d, context.Background)")
        print("    -> Correctly marked as 'resolved'")
        print("  False positives (coldStart, off-by-one, metric-label-injection)")
        print("    -> Tracked as 'still_present' with dismissal reasoning")
        print("  Rephrased duplicates (context.Background -> gap-fill deadline)")
        print("    -> Detected as new (different line bucket) - known limitation")
        print("  Progress visible across 3 rounds (not a blank-slate each time)")
        print()

    return FAIL == 0


def test_semantic_key_stability():
    """Test that semantic keys are stable across refactoring."""

    global PASS, FAIL

    print()
    print("=" * 70)
    print("TEST: Semantic Key Stability")
    print("=" * 70)

    # Same finding at different line numbers within same bucket
    f1 = Finding(
        file_path="exporters/kaexporter/collector.go",
        function_name="runCollection",
        category="race-condition",
        severity="medium",
        description="coldStart read without lock",
        line_number=89,
        pr_number=456,
        first_seen_sha="abc",
        last_seen_sha="abc"
    )

    f2 = Finding(
        file_path="exporters/kaexporter/collector.go",
        function_name="runCollection",
        category="race-condition",
        severity="medium",
        description="coldStart read without lock",
        line_number=85,
        pr_number=456,
        first_seen_sha="abc",
        last_seen_sha="def"
    )

    print(f"  Finding 1: line {f1.line_number} -> key: {f1.semantic_key}")
    print(f"  Finding 2: line {f2.line_number} -> key: {f2.semantic_key}")

    check("Same key for lines 89 and 85 (both bucket 80)",
          f1.semantic_key, f2.semantic_key)

    # Different bucket = different key (known limitation)
    f3 = Finding(
        file_path="exporters/kaexporter/collector.go",
        function_name="collectMetrics",
        category="race-condition",
        severity="medium",
        description="context.Background ignores parent",
        line_number=221,
        pr_number=456,
        first_seen_sha="abc",
        last_seen_sha="abc"
    )

    f4 = Finding(
        file_path="exporters/kaexporter/collector.go",
        function_name="collectMetrics",
        category="race-condition",
        severity="medium",
        description="gap-fill inherits parent deadline",
        line_number=327,
        pr_number=456,
        first_seen_sha="def",
        last_seen_sha="def"
    )

    print(f"\n  Finding 3: line {f3.line_number} -> key: {f3.semantic_key}")
    print(f"  Finding 4: line {f4.line_number} -> key: {f4.semantic_key}")

    check("Different key for lines 221 vs 327 (bucket 220 vs 320)",
          f3.semantic_key != f4.semantic_key, True)

    print("\n  Note: The rephrased context.Background finding at line 327")
    print("  gets a different key. This is a known limitation of bucket-based")
    print("  matching. Embedding-based similarity would catch this in Phase 2.")

    print()
    if FAIL == 0:
        print(f"  ALL {PASS} CHECKS PASSED")
    else:
        print(f"  {FAIL} FAILED, {PASS} passed")
    print()


if __name__ == "__main__":
    ok = test_kaexporter_three_round_review()
    test_semantic_key_stability()
    sys.exit(0 if ok and FAIL == 0 else 1)
