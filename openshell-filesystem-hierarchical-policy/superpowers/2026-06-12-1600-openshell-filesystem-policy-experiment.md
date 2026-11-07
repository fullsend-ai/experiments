# OpenShell Filesystem Policy Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** Build a bash orchestrator + Python probe that
validates Landlock read\_only/read\_write filesystem policy
enforcement inside an OpenShell sandbox, focusing on overlap
behavior where a read\_only subdirectory sits inside a
read\_write parent.

**Architecture:** A host-side bash script (`run.sh`) creates
an OpenShell sandbox with a declarative policy, seeds test
fixtures, SCPs a Python probe into the sandbox, and executes
it. The probe (`probe.py`) runs 24 filesystem assertions and
emits JSONL. The orchestrator parses results and prints a
summary table.

**Tech Stack:** Bash (orchestrator), Python 3 (probe),
OpenShell CLI, SSH/SCP.

**Spec:**
`docs/superpowers/specs/2026-06-12-openshell-filesystem-policy-test-design.md`

**Pattern to follow:**
`experiments/openshell-policy-bypass/run.sh`

---

## File Structure

```text
experiments/openshell-filesystem-policy/
├── run.sh         # Bash orchestrator (host-side)
├── probe.py       # Python probe (runs inside sandbox)
├── policy.yaml    # Filesystem policy under test
├── README.md      # Hypotheses, setup, results
└── .gitignore     # Exclude results/
```

- `policy.yaml` — static, checked in, the exact policy
  from the spec
- `probe.py` — self-contained, no dependencies beyond
  Python stdlib; emits one JSONL line per assertion
- `run.sh` — manages full lifecycle: prereqs → sandbox
  create → seed fixtures → run probe → parse → logs →
  cleanup; supports `--repo <owner/repo>` for real-repo
  mode
- `README.md` — hypotheses table, prerequisites, run
  instructions, results section to fill in after running

---

### Task 1: Scaffold experiment directory

**Files:**

- Create: `experiments/openshell-filesystem-policy/policy.yaml`
- Create: `experiments/openshell-filesystem-policy/.gitignore`

- [ ] **Step 1: Create the experiment directory**

```bash
mkdir -p experiments/openshell-filesystem-policy
```

- [ ] **Step 2: Write policy.yaml**

Write `experiments/openshell-filesystem-policy/policy.yaml`:

```yaml
version: 1

filesystem_policy:
  include_workdir: false
  read_only:
    - /usr
    - /lib
    - /proc
    - /dev/urandom
    - /app
    - /etc
    - /var/log
    - /sandbox/workspace/target-repo/
  read_write:
    - /sandbox
    - /tmp
    - /dev/null
```

- [ ] **Step 3: Write .gitignore**

Write `experiments/openshell-filesystem-policy/.gitignore`:

```text
results/
```

- [ ] **Step 4: Commit scaffold**

```bash
git add experiments/openshell-filesystem-policy/policy.yaml \
       experiments/openshell-filesystem-policy/.gitignore
git commit -m "chore(experiment): scaffold filesystem policy test

Assisted-by: Claude Code (Fable 5)"
```

---

### Task 2: Write probe.py

**Files:**

- Create: `experiments/openshell-filesystem-policy/probe.py`

This is the Python script that runs inside the sandbox. It
attempts 24 filesystem operations and emits JSONL results.
No external dependencies — stdlib only (`os`, `errno`,
`json`).

- [ ] **Step 1: Write probe.py with all 24 test cases**

Write `experiments/openshell-filesystem-policy/probe.py`:

```python
#!/usr/bin/env python3
"""Filesystem policy probe for OpenShell sandbox.

Runs 24 assertions against the active Landlock policy and
emits one JSON line per test to stdout. Always exits 0 so the
host orchestrator can parse results even when assertions fail.
"""

import errno
import json
import os


OVERLAP_BASE = "/sandbox/workspace/target-repo"


def emit(test_id, cat, op, path, expect, actual, passed,
         detail=""):
    print(
        json.dumps(
            {
                "id": test_id,
                "cat": cat,
                "op": op,
                "path": path,
                "expect": expect,
                "actual": actual,
                "pass": passed,
                "detail": detail,
            }
        ),
        flush=True,
    )


def ename(code):
    return errno.errorcode.get(code, f"errno={code}")


def try_read(path):
    try:
        if os.path.isdir(path):
            os.listdir(path)
        else:
            with open(path, "rb") as f:
                f.read(1)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_write(path, content=b"probe-test\n"):
    try:
        with open(path, "wb") as f:
            f.write(content)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_write_readback(path, content=b"probe-test\n"):
    actual, detail = try_write(path, content)
    if actual != "ok":
        return actual, detail
    try:
        with open(path, "rb") as f:
            got = f.read()
        if got != content:
            return "MISMATCH", f"wrote {content!r}, read {got!r}"
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), f"readback failed: {exc}"


def try_mkdir(path):
    try:
        os.mkdir(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_listdir(path):
    try:
        os.listdir(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_unlink(path):
    try:
        os.unlink(path)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def try_symlink_write(link_path, target, content=b"x\n"):
    try:
        os.symlink(target, link_path)
    except OSError as exc:
        return ename(exc.errno), f"symlink failed: {exc}"
    try:
        with open(link_path, "wb") as f:
            f.write(content)
        return "ok", ""
    except OSError as exc:
        return ename(exc.errno), str(exc)


def check(test_id, cat, op, path, expect, result):
    actual, detail = result
    emit(test_id, cat, op, path, expect, actual,
         actual == expect, detail)


def run_overlap():
    tr = OVERLAP_BASE
    check("1.1", "overlap", "read", f"{tr}/README.md", "ok",
          try_read(f"{tr}/README.md"))
    check("1.2", "overlap", "listdir", f"{tr}/", "ok",
          try_listdir(tr))
    check("1.3", "overlap", "write", f"{tr}/README.md",
          "EACCES", try_write(f"{tr}/README.md"))
    check("1.4", "overlap", "create", f"{tr}/new-file.txt",
          "EACCES", try_write(f"{tr}/new-file.txt"))
    check("1.5", "overlap", "mkdir", f"{tr}/newdir/",
          "EACCES", try_mkdir(f"{tr}/newdir"))
    sibling = "/sandbox/workspace/other-project"
    os.makedirs(sibling, exist_ok=True)
    check("1.6", "overlap", "write",
          f"{sibling}/file.txt", "ok",
          try_write(f"{sibling}/file.txt"))
    check("1.7", "overlap", "write",
          "/sandbox/workspace/file.txt", "ok",
          try_write("/sandbox/workspace/file.txt"))


def run_readwrite():
    check("2.1", "rw", "write+read", "/sandbox/test-rw",
          "ok", try_write_readback("/sandbox/test-rw"))
    check("2.2", "rw", "write+read", "/tmp/test-rw",
          "ok", try_write_readback("/tmp/test-rw"))
    check("2.3", "rw", "write", "/dev/null",
          "ok", try_write("/dev/null"))
    check("2.4", "rw", "mkdir", "/sandbox/newdir/",
          "ok", try_mkdir("/sandbox/newdir"))


def run_readonly():
    check("3.1", "ro", "read", "/usr/bin/ls",
          "ok", try_read("/usr/bin/ls"))
    check("3.2", "ro", "write", "/usr/test-write",
          "EACCES", try_write("/usr/test-write"))
    check("3.3", "ro", "read", "/etc/hostname",
          "ok", try_read("/etc/hostname"))
    check("3.4", "ro", "write", "/etc/test-write",
          "EACCES", try_write("/etc/test-write"))
    check("3.5", "ro", "read", "/proc/self/status",
          "ok", try_read("/proc/self/status"))
    check("3.6", "ro", "read", "/dev/urandom",
          "ok", try_read("/dev/urandom"))


def run_deny():
    check("4.1", "deny", "read", "/home/",
          "EACCES", try_listdir("/home"))
    check("4.2", "deny", "read", "/root/",
          "EACCES", try_listdir("/root"))
    check("4.3", "deny", "read", "/opt/",
          "EACCES", try_listdir("/opt"))
    check("4.4", "deny", "write", "/opt/test-write",
          "EACCES", try_write("/opt/test-write"))


def run_edge():
    check("5.1", "edge", "symlink_write",
          "/tmp/link-to-etc-passwd", "EACCES",
          try_symlink_write("/tmp/link-to-etc-passwd",
                            "/etc/passwd"))
    traversal = (
        "/sandbox/workspace/target-repo/../other/file"
    )
    os.makedirs("/sandbox/workspace/other", exist_ok=True)
    check("5.2", "edge", "traversal_write",
          traversal, "ok", try_write(traversal))
    check("5.3", "edge", "delete",
          f"{OVERLAP_BASE}/README.md", "EACCES",
          try_unlink(f"{OVERLAP_BASE}/README.md"))


def main():
    run_overlap()
    run_readwrite()
    run_readonly()
    run_deny()
    run_edge()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -m py_compile \
    experiments/openshell-filesystem-policy/probe.py
```

Expected: exits 0, no output.

- [ ] **Step 3: Verify JSONL output structure**

Run the probe locally. It will fail most assertions (no
sandbox enforcement, paths may not exist), but the output
format should be valid JSONL with the expected fields:

```bash
python3 experiments/openshell-filesystem-policy/probe.py \
    2>/dev/null \
    | head -3 \
    | python3 -c "
import json, sys
for line in sys.stdin:
    obj = json.loads(line)
    assert 'id' in obj, 'missing id'
    assert 'cat' in obj, 'missing cat'
    assert 'pass' in obj, 'missing pass'
    print(f'  {obj[\"id\"]:4s} {obj[\"cat\"]:8s} -> ok')
print('JSONL structure valid')
"
```

Expected: prints test IDs and "JSONL structure valid".
Some tests may error before producing output (missing
paths) — that's fine; we only need a few lines to
validate the format.

- [ ] **Step 4: Commit probe.py**

```bash
git add experiments/openshell-filesystem-policy/probe.py
git commit -m "feat(experiment): add filesystem policy probe

24-assertion Python probe testing Landlock read_only/read_write
enforcement across five categories: overlap, read-write,
read-only, deny, and edge cases.

Assisted-by: Claude Code (Fable 5)"
```

---

### Task 3: Write run.sh

**Files:**

- Create: `experiments/openshell-filesystem-policy/run.sh`

Host-side orchestrator following the pattern in
`experiments/openshell-policy-bypass/run.sh`. Manages the
full lifecycle: prereqs, sandbox creation, fixture seeding,
probe execution, result parsing, log collection, cleanup.

- [ ] **Step 1: Write run.sh**

Write `experiments/openshell-filesystem-policy/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
POLICY_FILE="$SCRIPT_DIR/policy.yaml"
PROBE_FILE="$SCRIPT_DIR/probe.py"
SANDBOX_NAME="fs-policy-test"

REPO="${1:-}"

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
    for i in $(seq 1 "$retries"); do
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x experiments/openshell-filesystem-policy/run.sh
```

- [ ] **Step 3: Validate with shellcheck**

```bash
shellcheck experiments/openshell-filesystem-policy/run.sh
```

Expected: exits 0 or only style warnings (SC2059 for
printf format strings with color codes is acceptable).
Fix any errors before proceeding.

- [ ] **Step 4: Validate syntax**

```bash
bash -n experiments/openshell-filesystem-policy/run.sh
```

Expected: exits 0, no output.

- [ ] **Step 5: Verify --help works**

```bash
experiments/openshell-filesystem-policy/run.sh --help
```

Expected: prints usage information and exits 0.

- [ ] **Step 6: Commit run.sh**

```bash
git add experiments/openshell-filesystem-policy/run.sh
git commit -m "feat(experiment): add filesystem policy orchestrator

Bash orchestrator that creates an OpenShell sandbox, seeds
fixtures, runs the Python probe, and reports results. Supports
--repo flag for testing against a real GitHub repository.

Assisted-by: Claude Code (Fable 5)"
```

---

### Task 4: Write README.md

**Files:**

- Create: `experiments/openshell-filesystem-policy/README.md`

- [ ] **Step 1: Write README.md**

Write
`experiments/openshell-filesystem-policy/README.md`:

````markdown
# OpenShell Filesystem Policy Test

Tests whether OpenShell's Landlock-based filesystem policy
correctly enforces read\_only/read\_write path restrictions.

**Primary question:** When a subdirectory is marked
`read_only` inside a parent marked `read_write`, does the
more-specific restriction win?

## Prerequisites

- OpenShell CLI installed and gateway running
  (`openshell gateway start`)
- Docker available (OpenShell uses it for sandboxes)

### For real-repo mode only

- GitHub CLI (`gh`) installed and authenticated

## Run

```shell
# Synthetic fixtures (no external dependencies)
./run.sh

# Real GitHub repo cloned into target-repo
./run.sh --repo octocat/Hello-World
```

## Hypotheses

| ID | Hypothesis                       | Tests    |
|----|----------------------------------|----------|
| H0 | Overlap: specific path wins      | 1.3–1.5  |
| H1 | Unlisted paths are inaccessible  | 4.1–4.4  |
| H2 | Read-only: reads ok, writes fail | 3.1–3.6  |
| H3 | Read-write: both operations work | 2.1–2.4  |
| H4 | Symlinks resolved before policy  | 5.1      |
| H5 | Traversal resolved before policy | 5.2      |
| H6 | include\_workdir: false honored  | all      |
| H7 | Runs on Fedora 44                | all      |

## Policy

See `policy.yaml`. Key detail: `include_workdir: false`
is required — the default is `true`, which would silently
add the workdir to `read_write` and mask the overlap
behavior.

## Results

Fill in after running.

### Assertion summary

| Cat     | Tests | Passed | Failed |
|---------|-------|--------|--------|
| overlap | 7     |        |        |
| rw      | 4     |        |        |
| ro      | 6     |        |        |
| deny    | 4     |        |        |
| edge    | 3     |        |        |
| Total   | 24    |        |        |

### Hypothesis outcomes

| ID | Status   | Notes |
|----|----------|-------|
| H0 |          |       |
| H1 |          |       |
| H2 |          |       |
| H3 |          |       |
| H4 |          |       |
| H5 |          |       |
| H6 |          |       |
| H7 |          |       |

## Environment

- **OpenShell version:**
- **Kernel:**
- **OS:**
- **Date:**
````

- [ ] **Step 2: Lint README.md**

```bash
markdownlint-cli2 \
    experiments/openshell-filesystem-policy/README.md
```

Expected: 0 errors. Fix any violations before committing.

- [ ] **Step 3: Commit README.md**

```bash
git add experiments/openshell-filesystem-policy/README.md
git commit -m "docs(experiment): add filesystem policy test README

Assisted-by: Claude Code (Fable 5)"
```

---

### Task 5: Integration validation

Run the full experiment against a live OpenShell instance
to validate that all components work together.

**Prerequisites:** OpenShell CLI installed, gateway running,
Docker available. This task runs on the actual machine —
it cannot be done in a dry-run or mock environment.

- [ ] **Step 1: Start the OpenShell gateway if needed**

```bash
openshell gateway info || openshell gateway start
```

- [ ] **Step 2: Run the experiment with synthetic fixtures**

```bash
cd experiments/openshell-filesystem-policy
./run.sh
```

Expected: the script creates a sandbox, seeds fixtures,
runs the probe, and prints a results table. All 24
assertions should pass.

If the script fails at sandbox creation (Fedora
compatibility issue — H7), document the error in
`README.md` and note that OpenShell still requires
Ubuntu/Debian.

- [ ] **Step 3: Review probe output**

```bash
cat results/probe-output.jsonl \
    | python3 -c "
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    status = 'PASS' if r['pass'] else 'FAIL'
    print(f'{status} {r[\"id\"]:4s} {r[\"cat\"]:8s} '
          f'{r[\"op\"]:18s} {r[\"expect\"]:8s} '
          f'-> {r[\"actual\"]}')
"
```

Verify:

- All "expect EACCES" tests show `actual: EACCES`
  (not ENOENT or EPERM)
- All "expect ok" tests show `actual: ok`
- 24 lines total

- [ ] **Step 4: Review sandbox logs**

```bash
cat results/sandbox-logs.txt
```

Check for any Landlock-related messages or unexpected
errors.

- [ ] **Step 5: Fill in README.md results**

Update the results tables in `README.md` with actual
pass/fail counts and hypothesis outcomes.

- [ ] **Step 6: Commit results update**

```bash
git add experiments/openshell-filesystem-policy/README.md
git commit -m "docs(experiment): record filesystem policy test results

Assisted-by: Claude Code (Fable 5)"
```

---

### Task 6: Optional — real repo mode

Only run this if Task 5 passed with synthetic fixtures
and you want to validate real-repo mode.

- [ ] **Step 1: Run with a real repo**

```bash
cd experiments/openshell-filesystem-policy
./run.sh --repo <owner/repo>
```

Substitute `<owner/repo>` with a repo you have read
access to.

- [ ] **Step 2: Compare results**

Results should be identical to synthetic mode — the
filesystem policy doesn't care about file content, only
paths.

- [ ] **Step 3: Update README.md if behavior differs**

If any assertions differ between synthetic and real-repo
mode, document the difference and investigate. The most
likely cause would be file permissions or ownership
differences from `git clone`.
