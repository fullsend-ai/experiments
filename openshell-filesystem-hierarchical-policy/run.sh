#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
POLICY_FILE="$SCRIPT_DIR/policies/policy.yaml"
PROBE_FILE="$SCRIPT_DIR/src/probe.py"
SANDBOX_NAME="fs-policy-test"

REPO=""

BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
DIM='\033[2m'
RESET='\033[0m'

step() {
    printf "\n${BOLD}${CYAN}▸ %s${RESET}\n\n" "$1"
}
pass() { printf "  ${GREEN}✓ %s${RESET}\n" "$1"; }
fail() { printf "  ${RED}✗ %s${RESET}\n" "$1"; }
warn() { printf "  ${YELLOW}⚠ %s${RESET}\n" "$1"; }
info() { printf "  ${DIM}%s${RESET}\n" "$1"; }

SSH_CONFIG=""
SSH_HOST=""

sandbox_exec() {
    ssh -F "$SSH_CONFIG" "$SSH_HOST" "$@" 2>&1
}

wait_for_ssh() {
    local retries=20
    for _i in $(seq 1 "$retries"); do
        if ssh -F "$SSH_CONFIG" "$SSH_HOST" \
            true >/dev/null 2>&1; then
            return 0
        fi
        sleep 3
    done
    fail "SSH connection timed out after $retries attempts"
    return 1
}

connect_sandbox() {
    SSH_CONFIG=$(mktemp)
    openshell sandbox ssh-config "$SANDBOX_NAME" \
        > "$SSH_CONFIG"
    SSH_HOST=$(awk '/^Host / { print $2; exit }' \
        "$SSH_CONFIG")
    wait_for_ssh
}

# ── Prerequisites ──────────────────────────────────────

check_prereqs() {
    step "Checking prerequisites"
    local ok=true

    if command -v openshell &>/dev/null; then
        pass "openshell CLI found"
    else
        fail "openshell CLI not found"
        ok=false
    fi

    if openshell gateway info &>/dev/null; then
        pass "openshell gateway running"
    else
        fail "openshell gateway not running"
        info "Run: openshell gateway start"
        ok=false
    fi

    if [[ -n "$REPO" ]]; then
        if ! command -v gh &>/dev/null; then
            fail "gh CLI not found (required for --repo)"
            ok=false
        elif ! gh auth status &>/dev/null; then
            fail "gh not authenticated"
            ok=false
        elif ! gh api "repos/$REPO" -q .full_name \
            &>/dev/null; then
            fail "Cannot access repo $REPO"
            ok=false
        else
            pass "Repo $REPO accessible"
        fi
    fi

    $ok || { echo "Prerequisites not met"; exit 1; }
}

# ── Fixtures ───────────────────────────────────────────

seed_fixtures() {
    step "Seeding test fixtures"

    if [[ -n "$REPO" ]]; then
        info "Cloning $REPO into target-repo..."
        sandbox_exec "git clone \
            https://github.com/$REPO.git \
            /sandbox/workspace/target-repo" || {
            fail "Failed to clone $REPO"
            return 1
        }
        pass "Cloned $REPO"
    else
        info "Creating synthetic fixtures..."
        sandbox_exec "mkdir -p \
            /sandbox/workspace/target-repo"
        sandbox_exec "echo '# Test repo' > \
            /sandbox/workspace/target-repo/README.md"
        pass "Created target-repo with README.md"
    fi
}

# ── Probe ──────────────────────────────────────────────

run_probe() {
    step "Running filesystem policy probe"
    mkdir -p "$RESULTS_DIR"

    info "Uploading probe.py..."
    scp -F "$SSH_CONFIG" "$PROBE_FILE" \
        "$SSH_HOST:/sandbox/probe.py"
    pass "Uploaded probe.py"

    info "Executing probe..."
    sandbox_exec "python3 /sandbox/probe.py" \
        > "$RESULTS_DIR/probe-output.jsonl" 2>&1
    pass "Probe complete"
}

# ── Results ────────────────────────────────────────────

parse_results() {
    step "Results"
    local total=0 passed=0 failed=0
    local output="$RESULTS_DIR/probe-output.jsonl"

    if [[ ! -f "$output" ]]; then
        fail "No probe output found"
        return 1
    fi

    printf "\n  %-5s %-8s %-18s %-25s %-8s %-8s\n" \
        "ID" "CAT" "OP" "PATH" "EXPECT" "RESULT"
    printf "  %s\n" \
        "$(printf '%.0s─' {1..76})"

    while IFS= read -r line; do
        local id cat op path expect actual pass_val
        id=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['id'])")
        cat=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['cat'])")
        op=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['op'])")
        path=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['path'])")
        expect=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['expect'])")
        actual=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['actual'])")
        pass_val=$(echo "$line" | python3 -c \
            "import json,sys; print(json.load(sys.stdin)['pass'])")

        total=$((total + 1))

        local icon
        if [[ "$pass_val" == "True" ]]; then
            passed=$((passed + 1))
            icon="${GREEN}✓${RESET}"
        else
            failed=$((failed + 1))
            icon="${RED}✗${RESET}"
        fi

        # Truncate long paths for display
        local short_path="$path"
        if [[ ${#path} -gt 25 ]]; then
            short_path="…${path: -24}"
        fi

        printf "  ${icon} %-4s %-8s %-18s %-25s %-8s %-8s\n" \
            "$id" "$cat" "$op" "$short_path" "$expect" \
            "$actual"
    done < "$output"

    printf "  %s\n" \
        "$(printf '%.0s─' {1..76})"
    printf "  Total: %d  " "$total"
    printf "${GREEN}Passed: %d${RESET}  " "$passed"
    if [[ $failed -gt 0 ]]; then
        printf "${RED}Failed: %d${RESET}\n" "$failed"
    else
        printf "Failed: 0\n"
    fi

    return "$failed"
}

# ── Logs ───────────────────────────────────────────────

collect_logs() {
    step "Collecting logs"
    mkdir -p "$RESULTS_DIR"
    openshell logs "$SANDBOX_NAME" --since 30m -n 200 \
        > "$RESULTS_DIR/sandbox-logs.txt" 2>&1 || true
    info "Logs saved to $RESULTS_DIR/"
}

# ── Cleanup ────────────────────────────────────────────

cleanup() {
    if [[ -n "$SSH_CONFIG" && -f "$SSH_CONFIG" ]]; then
        rm -f "$SSH_CONFIG"
    fi
    if openshell sandbox get "$SANDBOX_NAME" \
        &>/dev/null 2>&1; then
        info "Deleting sandbox $SANDBOX_NAME..."
        openshell sandbox delete "$SANDBOX_NAME" \
            2>/dev/null || true
    fi
}

# ── Main ───────────────────────────────────────────────

usage() {
    cat <<USAGE
Usage: run.sh [--repo <owner/repo>]

Options:
  --repo <owner/repo>  Clone a real GitHub repo into
                       target-repo instead of using
                       synthetic fixtures

Examples:
  ./run.sh                         # synthetic fixtures
  ./run.sh --repo octocat/Hello-World  # real repo
USAGE
}

main() {
    # Parse args
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --repo)
                REPO="${2:?--repo requires a value}"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown argument: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done

    echo ""
    printf "${BOLD}OpenShell Filesystem Policy Test${RESET}\n"
    if [[ -n "$REPO" ]]; then
        printf "${DIM}Mode: real repo ($REPO)${RESET}\n"
    else
        printf "${DIM}Mode: synthetic fixtures${RESET}\n"
    fi
    echo ""

    trap cleanup EXIT

    check_prereqs

    step "Creating sandbox"
    info "Name: $SANDBOX_NAME"
    info "Policy: $POLICY_FILE"
    openshell sandbox create \
        --name "$SANDBOX_NAME" \
        --policy "$POLICY_FILE" \
        --keep \
        --no-tty \
        --from base \
        -- true
    pass "Sandbox created"

    connect_sandbox
    pass "SSH connected"

    seed_fixtures
    run_probe

    local exit_code=0
    parse_results || exit_code=$?

    collect_logs

    if [[ $exit_code -eq 0 ]]; then
        printf "\n${BOLD}${GREEN}✓ All assertions passed.${RESET}\n"
    else
        printf "\n${BOLD}${RED}✗ %d assertion(s) failed.${RESET}\n" \
            "$exit_code"
    fi
    printf "  Results in: $RESULTS_DIR/\n\n"

    exit "$exit_code"
}

main "$@"
