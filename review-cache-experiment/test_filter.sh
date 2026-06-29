#!/bin/bash
#
# Test the classifier (Layer 3: State Classification)
#
# Verifies that findings are classified by lifecycle state:
# - new, still_present, dismissed
# - Dismissed findings are MARKED (not dropped) for publication policy

set -euo pipefail

cd "$(dirname "$0")"

echo "======================================================================"
echo "CLASSIFIER TEST - Layer 3: State Classification"
echo "======================================================================"

# Cleanup
rm -f test-filter.db
rm -f filtered-output.json

PR_NUMBER=999

echo ""
echo "📝 Step 1: Create test findings"
echo "----------------------------------------------------------------------"

cat > /tmp/test-agent-findings.json << 'EOF'
{
  "action": "request-changes",
  "findings": [
    {
      "severity": "high",
      "category": "auth-bypass",
      "file": "auth.go",
      "line": 42,
      "function": "CheckPermission",
      "description": "Missing permission check",
      "remediation": "Add validation"
    },
    {
      "severity": "medium",
      "category": "test-inadequate",
      "file": "handler_test.go",
      "line": 100,
      "function": "TestHandler",
      "description": "Missing edge case test",
      "remediation": "Add test"
    },
    {
      "severity": "low",
      "category": "naming-convention",
      "file": "utils.go",
      "line": 25,
      "function": "parseData",
      "description": "Should be snake_case",
      "remediation": "Rename to parse_data"
    }
  ]
}
EOF

echo "✓ Created 3 test findings"

echo ""
echo "🔒 Step 2: Dismiss one finding"
echo "----------------------------------------------------------------------"

python3 -c "
from scripts.store import ReviewMemoryStore

with ReviewMemoryStore('test-filter.db') as store:
    # Dismiss the auth-bypass finding
    store.dismiss_finding(
        'auth.go:CheckPermission:auth-bypass:40',
        ${PR_NUMBER},
        'Single-goroutine invariant - only main thread calls this',
        'senior-engineer'
    )
    print('✓ Dismissed: auth-bypass in auth.go:CheckPermission')
"

echo ""
echo "🔍 Step 3: Run classifier"
echo "----------------------------------------------------------------------"

python3 scripts/filter.py \
  --findings /tmp/test-agent-findings.json \
  --pr ${PR_NUMBER} \
  --db test-filter.db \
  --output filtered-output.json

echo ""
echo "📊 Step 4: Verify classification results"
echo "----------------------------------------------------------------------"

ORIGINAL_COUNT=$(jq '.findings | length' /tmp/test-agent-findings.json)
CLASSIFIED_COUNT=$(jq '.findings | length' filtered-output.json)

echo "Original findings: ${ORIGINAL_COUNT}"
echo "Classified findings: ${CLASSIFIED_COUNT}"

# Verify all findings are passed through (classifier doesn't drop)
if [ "$CLASSIFIED_COUNT" -ne "$ORIGINAL_COUNT" ]; then
  echo "✗ FAILED: Classifier dropped findings (should classify, not drop)"
  echo "  Expected: ${ORIGINAL_COUNT}, Got: ${CLASSIFIED_COUNT}"
  exit 1
fi
echo "✓ All findings passed through classifier"

# Check that auth-bypass was classified as 'dismissed'
AUTH_BYPASS_STATUS=$(jq -r '[.findings[] | select(.category == "auth-bypass")][0].status' filtered-output.json)
AUTH_BYPASS_REASON=$(jq -r '[.findings[] | select(.category == "auth-bypass")][0].dismissal_reason' filtered-output.json)

if [ "$AUTH_BYPASS_STATUS" = "dismissed" ]; then
  echo "✓ auth-bypass classified as 'dismissed'"
else
  echo "✗ FAILED: auth-bypass not classified as dismissed (status: ${AUTH_BYPASS_STATUS})"
  exit 1
fi

if [ "$AUTH_BYPASS_REASON" != "null" ] && [ -n "$AUTH_BYPASS_REASON" ]; then
  echo "✓ Dismissal reason preserved: ${AUTH_BYPASS_REASON}"
else
  echo "✗ FAILED: Dismissal reason missing"
  exit 1
fi

# Check that other findings are classified as 'new'
TEST_STATUS=$(jq -r '[.findings[] | select(.category == "test-inadequate")][0].status' filtered-output.json)
NAMING_STATUS=$(jq -r '[.findings[] | select(.category == "naming-convention")][0].status' filtered-output.json)

if [ "$TEST_STATUS" = "new" ] && [ "$NAMING_STATUS" = "new" ]; then
  echo "✓ Non-dismissed findings classified as 'new'"
else
  echo "✗ FAILED: Expected 'new' status for non-dismissed findings"
  echo "  test-inadequate: ${TEST_STATUS}, naming-convention: ${NAMING_STATUS}"
  exit 1
fi

# Verify action is unchanged (classifier doesn't modify verdict)
ORIGINAL_ACTION=$(jq -r '.action' /tmp/test-agent-findings.json)
CLASSIFIED_ACTION=$(jq -r '.action' filtered-output.json)

echo ""
echo "Action: ${ORIGINAL_ACTION} → ${CLASSIFIED_ACTION}"

if [ "${ORIGINAL_ACTION}" = "${CLASSIFIED_ACTION}" ]; then
  echo "✓ Action preserved (verdict calculation happens in publish.py)"
else
  echo "✗ FAILED: Classifier shouldn't modify action/verdict"
  exit 1
fi

echo ""
echo "🧪 Step 5: Test with no dismissals (passthrough)"
echo "----------------------------------------------------------------------"

rm -f test-filter-empty.db

python3 scripts/filter.py \
  --findings /tmp/test-agent-findings.json \
  --pr ${PR_NUMBER} \
  --db test-filter-empty.db \
  --output filtered-passthrough.json

PASSTHROUGH_COUNT=$(jq '.findings | length' filtered-passthrough.json)

if [ "$PASSTHROUGH_COUNT" -eq "$ORIGINAL_COUNT" ]; then
  echo "✓ All findings passed through (no dismissals in empty cache)"
else
  echo "✗ FAILED: Findings lost in passthrough mode"
  exit 1
fi

# Cleanup
rm -f test-filter.db test-filter-empty.db
rm -f filtered-output.json filtered-passthrough.json
rm -f /tmp/test-agent-findings.json

echo ""
echo "======================================================================"
echo "✅ CLASSIFIER TEST PASSED"
echo "======================================================================"
echo ""
echo "Verification:"
echo "  ✓ All findings passed through (classifier doesn't drop)"
echo "  ✓ Dismissed findings marked with status='dismissed'"
echo "  ✓ Dismissal reasons preserved in metadata"
echo "  ✓ Non-dismissed findings marked with status='new'"
echo "  ✓ Action/verdict preserved (publication policy decides later)"
echo "  ✓ Graceful passthrough when no cache exists"
echo ""
