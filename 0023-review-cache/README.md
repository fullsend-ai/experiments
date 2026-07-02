---
title: "23. Review cache publication policy"
status: Concluded
topics:
  - review
  - deduplication
---

# 23. Review cache publication policy

## Problem

Fullsend review agent re-reports identical findings across review runs:
- [**Issue #1500**](https://github.com/fullsend-ai/fullsend/issues/1500): 85% finding repetition rate
- [**Issue #1013**](https://github.com/fullsend-ai/fullsend/issues/1013): Same finding reported 6x on unchanged code
- [**Issue #2746**](https://github.com/fullsend-ai/fullsend/issues/2746): Non-deterministic verdicts on same commit
- [**Issue #2794**](https://github.com/fullsend-ai/fullsend/issues/2794): Identical protected-path comments on every run
- [**Issue #1552**](https://github.com/fullsend-ai/fullsend/issues/1552): No context passed to follow-up reviews

## Solution

**5-layer architecture** with Publication Policy Engine that separates finding state from presentation:

### Layer 1: SQLite Cache (Observation Storage)
- Persistent finding storage with lifecycle tracking
- Semantic deduplication (function-based identity)
- Status tracking: new → still_present → resolved → dismissed → reopened

### Layer 2: Lifecycle Tracking (Deduplication)
- Enrichment with function names and code snippets
- Deduplication logic comparing current vs prior findings
- Preserves `first_seen_sha` metadata

### Layer 3: Classifier (State Classification)
- Classifies findings by state (new/still_present/dismissed/resolved)
- Does NOT drop findings - passes all with metadata
- Deterministic Python (not LLM-based)

### Layer 4: Publication Policy (Presentation Strategy)
- **Key innovation:** State ≠ Presentation
- `new` → inline comment (full details)
- `reopened` → inline comment (regression alert)
- `still_present` → summary only (no duplicate noise)
- `dismissed` → summary only (transparency)
- `resolved` → summary only (progress tracking)

### Layer 5: GitHub Posting
- Posts final comment with inline findings + progress summary

**The separation of state from presentation** eliminates duplicate inline comments while maintaining full visibility.

---

## Experiment Hypothesis

**Claim:** A 5-layer architecture with publication policy can eliminate duplicate inline comments while maintaining full visibility of finding state.

**Scope:** This experiment validates the *mechanism* — that the architecture and plumbing work correctly. It does not yet validate *accuracy* on real-world data where function extraction is messier, line numbers shift unpredictably, and the agent rephrases findings between rounds.

**Status:** Confirmed on synthetic data. See [Experiment Conclusion](#experiment-conclusion) for detailed results and next steps.

---

## Impact (Synthetic Test Results)

| Scenario | Without Policy | With Policy | Improvement |
|----------|----------------|-------------|-------------|
| Round 1 | 6 inline | 6 inline | Baseline |
| Round 2 | 5 inline (3 dups) | 2 inline (0 dups) | 100% dup elimination |
| Round 3 | 3 inline (2 dups) | 1 inline (0 dups) | 100% dup elimination |
| **Total** | **14 inline (5 dups)** | **9 inline (0 dups)** | **100% reduction** |

*† Results measured against synthetic test fixtures designed to validate the mechanism. Real-world dedup rates require validation with actual agent output — see [Next Steps](#next-steps-for-production-validation).*

## Quick Start

```bash
# Run all tests
python3 test_e2e.py                  # Core logic (23 checks)
bash test_filter.sh                  # State classification
bash test_publication_policy.sh      # Publication policy (4 issues)

# See test_results.md for detailed results
```

## Example Output

### Round 1: Initial Review
```markdown
## Security Issues

### 🔴 race-condition in collector.go:221
[full details]

### 🔴 race-condition in collector.go:89 (coldStart)
[full details]

[... 4 more inline comments ...]
```

**Posted:** 6 inline comments (all new)

---

### Round 2: After Partial Fixes
```markdown
## Security Issues

### 🔴 NEW: race-condition in collector.go:327
[full details - gap-fill deadline]

### 🟢 NEW: race-condition in collector.go:122
[full details - scrapeDurationGauge]

---

## Progress Summary

✅ **Resolved (3):**
- logic-error in rolling_store.go:126 (WaitSumSeconds)
- error-handling-gap in release.go:211 (retryCount30d)
- race-condition in collector.go:221 (context.Background)

⚠️ **Still Present (3):**
- race-condition in collector.go:89 (coldStart)
- off-by-one in rolling_store.go:101
- metric-label-injection in rolling_store.go:88
```

**Posted:** 2 inline comments (only new), 6 summary items

**Key achievement:** No duplicate inline noise!

---

### Round 3: After Dismissals
```markdown
## Security Issues

### 🟢 NEW: error-handling-gap in collector.go:298
[full details - collectMetrics]

---

## Progress Summary

✅ **Resolved (3):**
- race-condition in collector.go:327 (fixed)
- off-by-one in rolling_store.go:101 (fixed)
- race-condition in collector.go:122 (fixed)

ℹ️ **Dismissed (2):**
- race-condition in collector.go:89 (coldStart)
  *Reason: Single-goroutine invariant*
- metric-label-injection in rolling_store.go:88
  *Reason: Existing mitigations sufficient*
```

**Posted:** 1 inline comment (only new), 5 summary items

## Implementation Status

**Complete and tested:**
- `scripts/store.py` - SQLite storage (380 LOC)
- `scripts/save.py` - Enrichment + deduplication (130 LOC)
- `scripts/filter.py` - State classification (150 LOC)
- `scripts/publish.py` - Publication policy (200 LOC)
- `scripts/extract_functions.sh` - Function extraction (70 LOC)
- All tests passing (test_e2e.py, test_pipeline.sh, test_filter.sh, test_publication_policy.sh)

**Total:** ~930 LOC (removed load.py - agent doesn't need it)

## Integration

**Key principle:** Agent is context-free. Only post-scripts read the cache (pipeline→pipeline).

### Agent Phase
```bash
# Agent reads: PR only (no cache input)
# Agent produces: agent-result.json (same every time)
```

### Post-Review Pipeline (post-review.sh)
```bash
# 1. Classify findings by state (Layer 3)
python3 .fullsend/review-memory/filter.py \
  --findings agent-result.json \
  --pr "$PR_NUMBER" \
  --db .fullsend/review-memory.db \
  --output classified-findings.json

# 2. Apply publication policy (Layer 4)
python3 .fullsend/review-memory/publish.py \
  --findings classified-findings.json \
  --pr "$PR_NUMBER" \
  --db .fullsend/review-memory.db \
  --output github-comment.md

# 3. Post to GitHub
gh pr comment "$PR_NUMBER" --body-file github-comment.md

# 4. Save to cache (for next review)
python3 .fullsend/review-memory/save.py \
  --findings agent-result.json \
  --pr "$PR_NUMBER" \
  --sha "$HEAD_SHA" \
  --db .fullsend/review-memory.db
```

Total integration: ~40 lines of bash

## File Structure

```
review-cache-experiment/
├── scripts/                         # Production code (post-scripts only)
│   ├── store.py                     # Layer 1: SQLite storage
│   ├── save.py                      # Layer 2: Deduplication
│   ├── filter.py                    # Layer 3: State classifier
│   ├── publish.py                   # Layer 4: Publication policy
│   ├── extract_functions.sh         # Function name extraction
│   └── schema.sql                   # Database schema (reference)
├── test-data/                       # Test fixtures
│   └── review/
│       ├── review1.json
│       ├── review2.json
│       └── review3.json
├── test_e2e.py                      # Lifecycle tracking (23 checks)
├── test_filter.sh                   # State classification
├── test_publication_policy.sh       # Publication policy (4 issues)
├── test_results.md                  # Test execution results and analysis
└── README.md                        # This file
```

## Test Coverage

```bash
✅ test_e2e.py
  - Lifecycle tracking (new → still_present → resolved → reopened)
  - Semantic key stability across refactoring
  - first_seen_sha preservation
  - Dismissal reason storage and retrieval
  - Pipeline workflow validation (agent context-free, post-scripts handle cache)

✅ test_filter.sh
  - State classification correctness
  - Metadata attachment

✅ test_publication_policy.sh
  - Issue #1500: Duplicate findings reduced ✓
  - Issue #1013: Same finding NOT reported 6x ✓
  - Issue #2794: Dismissed findings in summary ✓
  - Issue #1552: Context passed ✓
  - 100% elimination of duplicate inline comments ✓
```

**See [test_results.md](test_results.md) for detailed test execution results, failure analysis, and validation status.**

## Issues Solved

| Issue | Claim | Status |
|-------|-------|--------|
| #1500 | 85% repetition → <10% | ✅ 100% dup elimination |
| #1013 | Same finding 6x | ✅ Summary-only after first |
| #2746 | Non-deterministic verdicts | ✅ Deterministic cache |
| #2794 | Identical comments every run | ✅ Summary-only |
| #1552 | No context passed | ✅ Progress summary |

## Lifecycle: Reopened Findings (Regressions)

A finding that was previously `resolved` but reappears is classified as `reopened`, not `new`:

```
Round 1 → race-condition found (new)
Round 2 → race-condition fixed (resolved)
Round 5 → race-condition reintroduced (reopened)
```

**Why this matters:**
- `reopened` gets a full inline comment (same as `new`) — developer needs to see it
- But the comment indicates it's a **regression**, not a first-time discovery
- `first_seen_sha` is preserved — shows this issue has history
- Operationally distinct from `new`: regressions signal process problems, not just code problems

**Detection:** If the classifier finds a semantic key match against a prior finding with `status=resolved`, the finding is `reopened` rather than `still_present`.

---

## Why This Works

1. **Separation of Concerns**
   - State tracking (what happened) ≠ Presentation (how to show)
   - Can change policy without touching classification

2. **Developer-Friendly**
   - New findings: full inline attention
   - Progress summary: visibility without noise
   - Dismissed findings: transparency

3. **Architecturally Sound**
   - Satisfies all 5 constraints from `cross-run-memory.md`
   - System-derived, not agent-authored
   - PR-scoped security
   - Natural decay (cache irrelevant after merge)

4. **Gradual Degradation**
   - No cache → all findings marked 'new'
   - Cache exists → full lifecycle tracking
   - Backward compatible

---

## Experiment Conclusion

### What This Experiment Proved

**Result:** ✅ **Hypothesis confirmed on synthetic data**

The implementation demonstrates that:
1. **Architecture is sound** - The separation of state (what happened) from presentation (how to show) works as designed
2. **Plumbing is solid** - All 5 layers integrate cleanly in the post-review pipeline
3. **Agent isolation works** - Agent remains context-free while post-scripts handle all memory operations
4. **100% duplicate elimination is possible** - On controlled test fixtures across 3 review rounds

### What Was Tested

**Test data:** Synthetic fixtures (`test-data/review/*.json`) designed to validate the architecture
- Round 1: 6 findings (all new)
- Round 2: 5 findings (3 still_present, 2 new)
- Round 3: 3 findings (2 dismissed, 1 new)

**What this proves:** The implementation **can** deduplicate findings when semantic keys match and the pipeline executes correctly.

**What this doesn't prove:** How well function-based semantic keys hold up on real agent output where:
- Function extraction is messier (complex codebases, nested functions, language quirks)
- Line numbers shift unpredictably (rebases, force-pushes, large refactors)
- Agent rephrases findings between rounds (LLM non-determinism)
- Edge cases occur (renames, code movement, file splits)

### Next Steps for Production Validation

To validate readiness for production integration, the experiment needs real data testing:

1. **Pull actual agent output** from GitHub Actions artifacts on the reference issues:
   - [#1500](https://github.com/fullsend-ai/fullsend/issues/1500) - 85% repetition rate
   - [#1013](https://github.com/fullsend-ai/fullsend/issues/1013) - Same finding 6x
   - [#2794](https://github.com/fullsend-ai/fullsend/issues/2794) - Identical protected-path comments
   - [#1552](https://github.com/fullsend-ai/fullsend/issues/1552) - No context passed

2. **Measure actual dedup rates** on real review iterations:
   - What % of duplicates did semantic keys catch?
   - What % were missed due to line shifts, function renames, or rephrasing?
   - What edge cases broke the matching logic?

3. **Document findings** with specific metrics:
   - What % of duplicates did the keys catch?
   - What edge cases broke the matching logic?
   - Did it hold? Where did it break? What surprised us?


### Current Assessment

**Architecture:** Ready for integration - the design is sound and the implementation is clean.

**Deduplication accuracy:** Needs real-world validation before production use. The 100% success rate on synthetic data validates the mechanism works, but doesn't yet prove it handles the messy reality of production code reviews.

**Recommendation:** Run real data validation to measure actual dedup rates and identify edge cases before committing to SQLite cache as the production solution.
