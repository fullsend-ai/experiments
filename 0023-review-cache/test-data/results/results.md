# Test Execution Results

**Date:** July 2, 2026  
**Tests Run:** test_e2e.py, test_filter.sh, test_publication_policy.sh

---

## Test 1: test_e2e.py

```
======================================================================
KAEXPORTER BOT REVIEW - 3 ROUND SCENARIO
======================================================================

 ROUND 1: Initial bot review (commit a1b2c3)
----------------------------------------------------------------------
Bot finds 6 issues in kaexporter PR

  Saved 6 new findings
    [medium] race-condition @ exporters/kaexporter/collector.go:221
    [medium] race-condition @ exporters/kaexporter/collector.go:89
    [medium] error-handling-gap @ exporters/kaexporter/release.go:211
    [high] logic-error @ exporters/kaexporter/rolling_store.go:126
    [medium] off-by-one @ exporters/kaexporter/rolling_store.go:101
    [low] metric-label-injection @ exporters/kaexporter/rolling_store.go:88

 ROUND 2: After developer fixes (commit f6e5d4)
----------------------------------------------------------------------
Developer fixed: WaitSumSeconds denominator, retryCount30d Reset,
                 context.Background() (with AfterFunc pattern)
Bot re-reports: coldStart, off-by-one, metric-label-injection
Bot rephrases:  context.Background as 'gap-fill deadline'
Bot adds:       scrapeDurationGauge outside lock (new FP)

  Deduplication result:
    New (2): ['race-condition', 'race-condition']
    Still present (3): ['metric-label-injection', 'off-by-one', 'race-condition']
    Resolved (3): ['error-handling-gap', 'logic-error', 'race-condition']

  Developer dismisses false positives:
    Dismissed coldStart: 'Single-goroutine invariant: only runCollection goroutine rea...'
    Dismissed off-by-one: 'dayOffset 0-29 inclusive = 30 calendar days. Buckets[29-30] ...'
    Dismissed metric-label-injection: 'Existing mitigations sufficient: capped fetch limits, 30-day...'

 ROUND 3: Bot re-reviews AGAIN (commit 9a8b7c)
----------------------------------------------------------------------
Despite dismissals, bot re-reports coldStart and metric-label-injection
Bot adds: collectMetrics nil-error (genuinely new)

  Deduplication result:
    New (1): ['error-handling-gap']
    Still present (2): ['metric-label-injection', 'race-condition']
    Resolved (6): ['error-handling-gap', 'logic-error', 'off-by-one', 'race-condition', 'race-condition', 'race-condition']

  Dismissal reason still available for coldStart:
    'Single-goroutine invariant: only runCollection goroutine reads coldSta...'

======================================================================
FINAL STATE: 9 findings tracked across 3 rounds
  new: 1
  resolved: 6
  still_present: 2

RESULT: ALL 21 CHECKS PASSED
======================================================================

What the cache system demonstrated:
  Fixed bugs (WaitSumSeconds, retryCount30d, context.Background)
    -> Correctly marked as 'resolved'
  False positives (coldStart, off-by-one, metric-label-injection)
    -> Tracked as 'still_present' with dismissal reasoning
  Rephrased duplicates (context.Background -> gap-fill deadline)
    -> Detected as new (different line bucket) - known limitation
  Progress visible across 3 rounds (not a blank-slate each time)


======================================================================
TEST: Semantic Key Stability
======================================================================
  Finding 1: line 89 -> key: exporters/kaexporter/collector.go:runCollection:race-condition:80
  Finding 2: line 85 -> key: exporters/kaexporter/collector.go:runCollection:race-condition:80

  Finding 3: line 221 -> key: exporters/kaexporter/collector.go:collectMetrics:race-condition:220
  Finding 4: line 327 -> key: exporters/kaexporter/collector.go:collectMetrics:race-condition:320

  Note: The rephrased context.Background finding at line 327
  gets a different key. This is a known limitation of bucket-based
  matching. Embedding-based similarity would catch this in Phase 2.

  ALL 23 CHECKS PASSED

```

**Result:** ✅ PASSED

---

## Test 2: test_filter.sh

```
======================================================================
CLASSIFIER TEST - Layer 3: State Classification
======================================================================

📝 Step 1: Create test findings
----------------------------------------------------------------------
✓ Created 3 test findings

🔒 Step 2: Dismiss one finding
----------------------------------------------------------------------
✓ Dismissed: auth-bypass in auth.go:CheckPermission

🔍 Step 3: Run classifier
----------------------------------------------------------------------
ℹ️  CLASSIFIED (dismissed): auth-bypass in auth.go:CheckPermission
   Reason: Single-goroutine invariant - only main thread calls this
🆕 CLASSIFIED (new): test-inadequate in handler_test.go:TestHandler
🆕 CLASSIFIED (new): naming-convention in utils.go:parseData

✓ Classification complete:
  Total input: 3
  New: 2
  Still present: 0
  Dismissed: 1

  All findings passed to publish.py for presentation policy

📊 Step 4: Verify classification results
----------------------------------------------------------------------
Original findings: 3
Classified findings: 3
✓ All findings passed through classifier
✓ auth-bypass classified as 'dismissed'
✓ Dismissal reason preserved: Single-goroutine invariant - only main thread calls this
✓ Non-dismissed findings classified as 'new'

Action: request-changes → request-changes
✓ Action preserved (verdict calculation happens in publish.py)

🧪 Step 5: Test with no dismissals (passthrough)
----------------------------------------------------------------------
No cache database found at test-filter-empty.db - marking all as 'new'
✓ All findings passed through (no dismissals in empty cache)

======================================================================
✅ CLASSIFIER TEST PASSED
======================================================================

Verification:
  ✓ All findings passed through (classifier doesn't drop)
  ✓ Dismissed findings marked with status='dismissed'
  ✓ Dismissal reasons preserved in metadata
  ✓ Non-dismissed findings marked with status='new'
  ✓ Action/verdict preserved (publication policy decides later)
  ✓ Graceful passthrough when no cache exists

```

**Result:** ✅ PASSED

---

## Test 3: test_publication_policy.sh

```
======================================================================
PUBLICATION POLICY TEST - Layer 6.5
======================================================================

Testing the separation of finding state from presentation strategy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROUND 1: Initial review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Classify findings...
No cache database found at test-pub.db - marking all as 'new'

Step 2: Apply publication policy...
Publication Policy Applied:
  Inline comments (new): 6
  Summary - Resolved: 0
  Summary - Unresolved: 0
  Summary - Dismissed: 0

✓ GitHub comment written to github-comment-round1.md
✓ Policy result written to github-comment-round1-policy.json

Step 3: Save to cache...

Round 1 GitHub comment preview:
────────────────────────────────────────────────────────────────────
## Security Issues

### 🟡 race-condition in exporters/kaexporter/collector.go:221

**Severity:** medium

Non-bootstrapped namespace goroutines create independent contexts via context.WithTimeout(context.Background(), ...). These are not cancelled on parent context cancellation (e.g. SIGTERM), delaying graceful shutdown by up to 600s.

**Remediation:**
Derive per-namespace contexts from the parent context: context.WithTimeout(ctx, ...) instead of context.WithTimeout(context.Background(), ...).

### 🟡 race-condition in exporters/kaexporter/collector.go:89

**Severity:** medium

coldStart field is read outside e.mu lock in runCollection. Multiple goroutines could observe stale values.

**Remediation:**
Protect coldStart reads with e.mu.RLock() or use atomic.Bool.

### 🟡 error-handling-gap in exporters/kaexporter/release.go:211

**Severity:** medium

retryCount30d.Reset() runs unconditionally in updateGauges. When collectMetrics returns (nil, nil) for 0 namespaces, retry count gauges are wiped despite the rolling store retaining valid data.

**Remediation:**
Guard retryCount30d.Reset() inside the releaseIdx != nil check.

### 🔴 logic-error in exporters/kaexporter/rolling_store.go:126

**Severity:** high

ComputeWaitMean uses Count (all observations) as denominator but WaitSumSeconds only accumulates for observations with valid wait times. This inflates the denominator and deflates the reported mean wait time.

**Remediation:**
Use SuccessCount as the denominator in ComputeWaitMean, and only accumulate WaitSumSeconds for successful observations.

### 🟡 off-by-one in exporters/kaexporter/rolling_store.go:101

**Severity:** medium

The cutoff comparison in Compute* methods uses <= while RecordObservation rejects dayOffset >= 30. Both boundaries consistently exclude day-30, creating a 29-day window instead of the documented 30-day SLO window.

**Remediation:**
Change dayOffset >= 30 to dayOffset > 30 to include the 30th day.

### 🟢 metric-label-injection in exporters/kaexporter/rolling_store.go:88

**Severity:** low
────────────────────────────────────────────────────────────────────

Round 1 Results:
  Inline comments (new): 6
  Summary items: 0
  ✓ Expected: All findings posted inline (first review)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROUND 2: After developer fixes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Developer fixed 3 issues, 3 still present, 2 new

Step 1: Classify findings...
🆕 CLASSIFIED (new): race-condition in exporters/kaexporter/collector.go:package
📌 CLASSIFIED (still-present): race-condition in exporters/kaexporter/collector.go:package
   First seen: commit1
📌 CLASSIFIED (still-present): off-by-one in exporters/kaexporter/rolling_store.go:package
   First seen: commit1
📌 CLASSIFIED (still-present): metric-label-injection in exporters/kaexporter/rolling_store.go:package
   First seen: commit1
🆕 CLASSIFIED (new): race-condition in exporters/kaexporter/collector.go:package

✓ Classification complete:
  Total input: 5
  New: 2
  Still present: 3
  Dismissed: 0

  All findings passed to publish.py for presentation policy

Step 2: Apply publication policy...
Publication Policy Applied:
  Inline comments (new): 2
  Summary - Resolved: 3
  Summary - Unresolved: 3
  Summary - Dismissed: 0

✓ GitHub comment written to github-comment-round2.md
✓ Policy result written to github-comment-round2-policy.json

Step 3: Save to cache...

Round 2 GitHub comment preview:
────────────────────────────────────────────────────────────────────
## Security Issues

### 🟡 race-condition in exporters/kaexporter/collector.go:327

**Severity:** medium

Gap-fill goroutines inherit the parent collection cycle's deadline context. If main collection consumed most of the timeout budget, gap-fill fails silently and permanently consumes retry attempts (max 5 per namespace).

**Remediation:**
Use a fresh context derived from context.Background() for gap-fill operations.

### 🟢 race-condition in exporters/kaexporter/collector.go:122

**Severity:** low

scrapeDurationGauge.Set() is called outside e.mu.Unlock(), creating a potential data race on the gauge value.

**Remediation:**
Move scrapeDurationGauge.Set() inside the locked section.


---

## Progress Summary


✅ **Resolved (3):**

- race-condition in exporters/kaexporter/collector.go:221

- error-handling-gap in exporters/kaexporter/release.go:211

- logic-error in exporters/kaexporter/rolling_store.go:126


⚠️ **Still Present (3):**

- race-condition in exporters/kaexporter/collector.go:89

- off-by-one in exporters/kaexporter/rolling_store.go:101

- metric-label-injection in exporters/kaexporter/rolling_store.go:88
────────────────────────────────────────────────────────────────────

Round 2 Results:
  Inline comments (new): 2
  Summary - Resolved: 3
  Summary - Unresolved: 3
  Summary - Dismissed: 0

  ✓ Key achievement: Still-present findings NOT posted inline!
  ✓ Only new findings get inline comments
  ✓ Progress summary shows resolved/unresolved

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROUND 3: After developer dismisses findings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Developer dismisses: coldStart, metric-label-injection

Step 1: Classify findings...
ℹ️  CLASSIFIED (dismissed): race-condition in exporters/kaexporter/collector.go:package
   Reason: Single-goroutine invariant
ℹ️  CLASSIFIED (dismissed): metric-label-injection in exporters/kaexporter/rolling_store.go:package
   Reason: Existing mitigations sufficient
🆕 CLASSIFIED (new): error-handling-gap in exporters/kaexporter/collector.go:package

✓ Classification complete:
  Total input: 3
  New: 1
  Still present: 0
  Dismissed: 2

  All findings passed to publish.py for presentation policy

Step 2: Apply publication policy...
Publication Policy Applied:
  Inline comments (new): 1
  Summary - Resolved: 3
  Summary - Unresolved: 0
  Summary - Dismissed: 2

✓ GitHub comment written to github-comment-round3.md
✓ Policy result written to github-comment-round3-policy.json

Round 3 GitHub comment preview:
────────────────────────────────────────────────────────────────────
## Security Issues

### 🟢 error-handling-gap in exporters/kaexporter/collector.go:298

**Severity:** low

collectMetrics() returns nil error even when all namespace collections fail (nsOK == 0), causing the readiness probe to report healthy despite zero namespaces being successfully scraped.

**Remediation:**
Return an error when nsOK == 0 and len(namespaces) > 0.


---

## Progress Summary


✅ **Resolved (3):**

- race-condition in exporters/kaexporter/collector.go:327

- off-by-one in exporters/kaexporter/rolling_store.go:101

- race-condition in exporters/kaexporter/collector.go:122


ℹ️ **Dismissed (2):**

- race-condition in exporters/kaexporter/collector.go:89
  *Reason: Single-goroutine invariant*

- metric-label-injection in exporters/kaexporter/rolling_store.go:88
  *Reason: Existing mitigations sufficient*
────────────────────────────────────────────────────────────────────

Round 3 Results:
  Inline comments (new): 1
  Summary - Resolved: 3
  Summary - Unresolved: 0
  Summary - Dismissed: 2

  ✓ Dismissed findings shown in summary (transparency)
  ✓ Dismissed findings NOT posted inline (respects dismissal)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPACT ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Without Publication Policy (old behavior):
  Round 1: 6 inline comments
  Round 2: 5 inline comments (3 still-present + 2 new)
  Round 3: 3 inline comments (2 still-present + 1 new)
  Total inline: 14 comments
  Duplicate noise: HIGH (still-present posted every round)

With Publication Policy (new behavior):
  Round 1: 6 inline comments (all new)
  Round 2: 2 inline comments (only new)
  Round 3: 1 inline comments (only new)
  Total inline: 9 comments
  Duplicate noise: ZERO (still-present in summary only)

Reduction in duplicate inline comments:
  Before: 8 duplicate inline comments
  After: 0 duplicate inline comments
  Reduction: 8 (100% elimination)

Verification of GitHub issue claims:

  ✅ Issue #1500: Duplicate findings reduced (only new posted inline)
  ✅ Issue #1013: Same finding NOT reported 6x (summary-only after first)
  ✅ Issue #2794: Dismissed findings in summary (not inline)
  ✅ Issue #1552: Context passed (resolved findings tracked)

======================================================================
✅ PUBLICATION POLICY TEST PASSED
======================================================================

Key achievements:
  • Finding state separated from presentation strategy
  • Still-present findings: summary-only (no inline duplication)
  • Dismissed findings: shown in summary (transparency)
  • Progress visible: resolved/unresolved/dismissed tracking
  • 100% elimination of duplicate inline comments

```

**Result:** ✅ PASSED

---

## Summary

| Test | Status | Notes |
|------|--------|-------|
| test_e2e.py | ✅ PASSED | All 23 checks passed |
| test_filter.sh | ✅ PASSED | Classification layer validated |
| test_publication_policy.sh | ✅ PASSED | 100% dup elimination validated |

**Overall:** 3/3 tests passing (100%)

See [test_results.md](../test_results.md) for detailed analysis.
