#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
STATE_FILE="${SCRIPT_DIR}/.experiment-state"

BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
DIM='\033[2m'
RESET='\033[0m'

step() { printf "\n${BOLD}${CYAN}▸ %s${RESET}\n\n" "$1"; }
pass() { printf "  ${GREEN}✓ %s${RESET}\n" "$1"; }
fail() { printf "  ${RED}✗ %s${RESET}\n" "$1"; exit 1; }
info() { printf "  ${DIM}%s${RESET}\n" "$1"; }

# ── Load state ─────────────────────────────────────────────────────
if [[ ! -f "${STATE_FILE}" ]]; then
  fail "No .experiment-state found. Run ./setup-target-repo.sh first."
fi
while IFS='=' read -r key value; do
  case "$key" in
    TARGET_ORG|TARGET_REPO|FULL_REPO|ISSUE_NUMBER|ISSUE_URL)
      declare "$key=$value" ;;
  esac
done < "${STATE_FILE}"
info "Repo: ${FULL_REPO}"
info "Issue: #${ISSUE_NUMBER}"

# ── Resolve fullsend-dir ───────────────────────────────────────────
# FULLSEND_DIR should point to the fullsend scaffold directory containing
# harness/, agents/, skills/, policies/, scripts/, and env/.
# Typically: /path/to/fullsend/internal/scaffold/fullsend-repo
FULLSEND_DIR="${FULLSEND_DIR:?Set FULLSEND_DIR to the fullsend scaffold directory (e.g., /path/to/fullsend/internal/scaffold/fullsend-repo)}"
if [[ ! -f "${FULLSEND_DIR}/harness/triage.yaml" ]]; then
  fail "FULLSEND_DIR does not contain harness/triage.yaml: ${FULLSEND_DIR}"
fi

# ── Prerequisites ──────────────────────────────────────────────────
step "Checking prerequisites"
for cmd in fullsend gh git; do
  if command -v "$cmd" &>/dev/null; then
    pass "$cmd found"
  else
    fail "$cmd not found"
  fi
done

for var in ANTHROPIC_VERTEX_PROJECT_ID CLOUD_ML_REGION GOOGLE_APPLICATION_CREDENTIALS; do
  if [[ -n "${!var:-}" ]]; then
    pass "${var} set"
  else
    fail "${var} not set"
  fi
done

# ── Sanitize function ─────────────────────────────────────────────
sanitize_file() {
  local file="$1"
  [[ -f "${file}" ]] || return 0

  sed \
    -e "s|${GH_TOKEN:-__no_token__}|***|g" \
    -e "s|${ANTHROPIC_VERTEX_PROJECT_ID}|***|g" \
    -e "s|${GOOGLE_APPLICATION_CREDENTIALS}|***|g" \
    -e 's|ghp_[A-Za-z0-9]\{36\}|***|g' \
    -e 's|ghu_[A-Za-z0-9]\{36\}|***|g' \
    -e 's|ghs_[A-Za-z0-9]\{36\}|***|g' \
    -e 's|gho_[A-Za-z0-9]\{36\}|***|g' \
    -e 's|github_pat_[A-Za-z0-9_]\{82\}|***|g' \
    -e 's|ya29\.[A-Za-z0-9_-]\{50,\}|***|g' \
    -e 's|[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}|***.***.***.***|g' \
    -e 's|[a-zA-Z0-9._%+-]\+@[a-zA-Z0-9.-]\+\.iam\.gserviceaccount\.com|***@***.iam.gserviceaccount.com|g' \
    "${file}" > "${file}.tmp" && mv "${file}.tmp" "${file}"
}

sanitize_results() {
  local dir="$1"
  step "Sanitizing results in ${dir}"
  for f in "${dir}"/*.json "${dir}"/*.jsonl; do
    if [[ -f "$f" ]]; then
      sanitize_file "$f"
      pass "Sanitized $(basename "$f")"
    fi
  done
}

# ── Run function ───────────────────────────────────────────────────
run_triage() {
  local label="$1"
  local output_dir="${RESULTS_DIR}/${label}"
  local repo_dir

  step "Running triage (${label})"

  # Clone target repo to a temp dir.
  repo_dir=$(mktemp -d)
  local run_output_dir
  run_output_dir=$(mktemp -d)
  trap 'rm -rf "${repo_dir}" "${run_output_dir}"' RETURN

  git clone "git@github.com:${FULL_REPO}.git" "${repo_dir}/repo"
  info "Cloned to ${repo_dir}/repo"

  local rc=0
  GITHUB_ISSUE_URL="${ISSUE_URL}" \
  GH_TOKEN="${GH_TOKEN:-$(gh auth token)}" \
  fullsend run triage \
    --fullsend-dir "${FULLSEND_DIR}" \
    --target-repo "${repo_dir}/repo" \
    --output-dir "${run_output_dir}" \
    || rc=$?

  if [[ $rc -ne 0 ]]; then
    info "Warning: fullsend exited with rc=${rc} — collecting partial results"
  fi

  # Collect results.
  mkdir -p "${output_dir}"

  # Copy agent result JSON.
  local result_json
  result_json=$(find "${run_output_dir}" -name "agent-result.json" -print -quit 2>/dev/null || true)
  if [[ -n "${result_json}" ]]; then
    cp "${result_json}" "${output_dir}/agent-result.json"
    pass "Agent result saved"
  else
    info "No agent-result.json found"
  fi

  # Copy transcript JSONL.
  local transcript
  transcript=$(find "${run_output_dir}" -name "*.jsonl" -path "*/transcripts/*" -print -quit 2>/dev/null || true)
  if [[ -n "${transcript}" ]]; then
    cp "${transcript}" "${output_dir}/transcript.jsonl"
    pass "Transcript saved"
  else
    info "No transcript found"
  fi

  sanitize_results "${output_dir}"

  pass "${label} run complete"
}

# ── Control run ────────────────────────────────────────────────────
run_triage "control"

# ── Add skill to target repo ──────────────────────────────────────
step "Adding triage-guidance skill to target repo"
SKILL_WORK_DIR=$(mktemp -d)
git clone "git@github.com:${FULL_REPO}.git" "${SKILL_WORK_DIR}/repo"
cp -r "${SCRIPT_DIR}/skill-files/.claude" "${SKILL_WORK_DIR}/repo/"
git -C "${SKILL_WORK_DIR}/repo" add -A
git -C "${SKILL_WORK_DIR}/repo" commit -m "Add .claude/skills/triage-guidance for experiment"
git -C "${SKILL_WORK_DIR}/repo" push origin main
rm -rf "${SKILL_WORK_DIR}"
pass "Skill committed and pushed"

# ── Treatment run ──────────────────────────────────────────────────
run_triage "treatment"

# ── Summary ────────────────────────────────────────────────────────
step "Experiment complete"
echo ""
echo "Results saved to:"
echo "  ${RESULTS_DIR}/control/"
echo "  ${RESULTS_DIR}/treatment/"
echo ""
echo "To check skill discovery (primary evidence):"
echo "  grep -l 'triage-guidance' results/treatment/transcript.jsonl"
echo ""
echo "To compare triage outputs:"
echo "  diff <(jq . results/control/agent-result.json) <(jq . results/treatment/agent-result.json)"