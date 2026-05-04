#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ORG="${TARGET_ORG:-maruiz93}"
TARGET_REPO="${TARGET_REPO:-experiment-target-repo-skills}"
FULL_REPO="${TARGET_ORG}/${TARGET_REPO}"

BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'

step() { printf "\n${BOLD}${CYAN}▸ %s${RESET}\n" "$1"; }
pass() { printf "  ${GREEN}✓ %s${RESET}\n" "$1"; }
fail() { printf "  ${RED}✗ %s${RESET}\n" "$1"; exit 1; }

# ── Prerequisites ──────────────────────────────────────────────────
step "Checking prerequisites"
for cmd in gh git; do
  if command -v "$cmd" &>/dev/null; then
    pass "$cmd found"
  else
    fail "$cmd not found"
  fi
done

# ── Create repo ────────────────────────────────────────────────────
step "Creating GitHub repo ${FULL_REPO}"
if gh repo view "${FULL_REPO}" &>/dev/null; then
  pass "Repo already exists"
else
  gh repo create "${FULL_REPO}" --public --description "Synthetic repo for target-repo-skills experiment"
  pass "Repo created"
fi

# ── Push source files ──────────────────────────────────────────────
step "Pushing source files"
WORK_DIR=$(mktemp -d)
trap 'rm -rf "${WORK_DIR}"' EXIT

git -C "${WORK_DIR}" init -b main
cp -r "${SCRIPT_DIR}/target-repo-files/"* "${WORK_DIR}/"

git -C "${WORK_DIR}" add -A
git -C "${WORK_DIR}" commit -m "Initial commit: minimal Go REST API"
git -C "${WORK_DIR}" remote add origin "git@github.com:${FULL_REPO}.git"
git -C "${WORK_DIR}" push -u origin main --force
pass "Source files pushed"

# ── Create labels ──────────────────────────────────────────────────
step "Creating labels"
LABELS=(
  "area:api:#0e8a16"
  "area:data:#1d76db"
  "area:config:#5319e7"
  "priority:critical:#b60205"
  "priority:high:#d93f0b"
  "priority:medium:#fbca04"
  "type:feature:#a2eeef"
  "type:bug:#d73a4a"
  "type:performance:#f9d0c4"
)
for entry in "${LABELS[@]}"; do
  IFS=: read -r prefix name color <<< "${entry}"
  label="${prefix}:${name}"
  if gh label create "${label}" --repo "${FULL_REPO}" --color "${color#\#}" --force 2>/dev/null; then
    pass "Label: ${label}"
  else
    pass "Label: ${label} (already exists)"
  fi
done

# ── File issue ─────────────────────────────────────────────────────
step "Filing test issue"
ISSUE_TITLE="/users endpoint returns 500 when database is unreachable"
ISSUE_BODY="When the PostgreSQL connection drops, hitting \`GET /users\` returns a 500 Internal Server Error with a panic in the logs.

\`\`\`
goroutine 1 [running]:
github.com/example/userapi/handlers.ListUsers(...)
    handlers/users.go:25
\`\`\`

Expected behavior: return 503 Service Unavailable with an appropriate error message instead of panicking.

Steps to reproduce:
1. Start the server with \`go run .\`
2. Stop PostgreSQL
3. Send \`GET /users\`
4. Observe 500 with panic trace"

ISSUE_URL=$(gh issue create \
  --repo "${FULL_REPO}" \
  --title "${ISSUE_TITLE}" \
  --body "${ISSUE_BODY}" \
  --label "bug")

ISSUE_NUMBER=$(basename "${ISSUE_URL}")
pass "Issue #${ISSUE_NUMBER} created: ${ISSUE_URL}"

# ── Save state ─────────────────────────────────────────────────────
STATE_FILE="${SCRIPT_DIR}/.experiment-state"
cat > "${STATE_FILE}" <<EOF
TARGET_ORG=${TARGET_ORG}
TARGET_REPO=${TARGET_REPO}
FULL_REPO=${FULL_REPO}
ISSUE_NUMBER=${ISSUE_NUMBER}
ISSUE_URL=${ISSUE_URL}
EOF
pass "State saved to ${STATE_FILE}"

echo ""
echo "Setup complete. Run ./run.sh to execute the experiment."