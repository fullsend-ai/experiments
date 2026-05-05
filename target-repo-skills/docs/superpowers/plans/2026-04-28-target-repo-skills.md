# Target Repository Skills Experiment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an experiment that tests whether a target repository's `.claude/skills/` are discovered and used by the fullsend triage agent running inside an OpenShell sandbox.

**Architecture:** Two shell scripts (`setup-target-repo.sh` and `run.sh`) create a synthetic GitHub repo and run fullsend's triage agent against it twice — once without `.claude/skills/` (control) and once with a triage guidance skill (treatment). Results are captured as JSONL transcripts and triage JSON output.

**Tech Stack:** Bash, gh CLI, fullsend CLI, Git

---

## File Structure

```
target-repo-skills/
├── README.md                        # Experiment documentation
├── HOW_TO.md                        # Reproduction steps
├── setup-target-repo.sh             # Creates synthetic GitHub repo + files issue
├── run.sh                           # Runs control/treatment, captures output
├── target-repo-files/               # Source files committed to the synthetic repo
│   ├── go.mod
│   ├── main.go
│   ├── handlers/
│   │   ├── users.go
│   │   └── health.go
│   └── README.md
├── skill-files/                     # Skill added for the treatment run
│   └── .claude/
│       └── skills/
│           └── triage-guidance/
│               └── SKILL.md
├── docs/
│   ├── 2026-04-28-target-repo-skills-design.md
│   └── superpowers/
│       └── plans/
│           └── 2026-04-28-target-repo-skills.md    # This file
└── results/
    ├── control/
    └── treatment/
```

**Key decisions:**
- Target repo source files live in `target-repo-files/` so `setup-target-repo.sh` can push them verbatim.
- The skill lives in `skill-files/` with the full `.claude/skills/` path so `run.sh` can copy the tree into a clone and push.
- Scripts are self-contained — no Python, no dependencies beyond `gh`, `git`, and `fullsend`.

---

### Task 1: Create the synthetic Go source files

**Files:**
- Create: `target-repo-files/go.mod`
- Create: `target-repo-files/main.go`
- Create: `target-repo-files/handlers/users.go`
- Create: `target-repo-files/handlers/health.go`
- Create: `target-repo-files/README.md`

These files are committed to the synthetic GitHub repo by `setup-target-repo.sh`. They need to be a plausible Go REST API — enough for the triage agent to reason about.

- [ ] **Step 1: Create `target-repo-files/go.mod`**

```
target-repo-files/go.mod
```

```go
module github.com/example/userapi

go 1.22
```

- [ ] **Step 2: Create `target-repo-files/main.go`**

```
target-repo-files/main.go
```

```go
package main

import (
	"log"
	"net/http"

	"github.com/example/userapi/handlers"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /users", handlers.ListUsers)
	mux.HandleFunc("GET /users/{id}", handlers.GetUser)
	mux.HandleFunc("POST /users", handlers.CreateUser)

	log.Println("listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", mux))
}
```

- [ ] **Step 3: Create `target-repo-files/handlers/users.go`**

```
target-repo-files/handlers/users.go
```

```go
package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
)

var db *sql.DB

type User struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

func ListUsers(w http.ResponseWriter, r *http.Request) {
	rows, err := db.Query("SELECT id, name, email FROM users")
	if err != nil {
		panic(err)
	}
	defer rows.Close()

	var users []User
	for rows.Next() {
		var u User
		if err := rows.Scan(&u.ID, &u.Name, &u.Email); err != nil {
			panic(err)
		}
		users = append(users, u)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(users)
}

func GetUser(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var u User
	err := db.QueryRow("SELECT id, name, email FROM users WHERE id = $1", id).
		Scan(&u.ID, &u.Name, &u.Email)
	if err != nil {
		panic(err)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(u)
}

func CreateUser(w http.ResponseWriter, r *http.Request) {
	var u User
	if err := json.NewDecoder(r.Body).Decode(&u); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	_, err := db.Exec("INSERT INTO users (name, email) VALUES ($1, $2)", u.Name, u.Email)
	if err != nil {
		panic(err)
	}

	w.WriteHeader(http.StatusCreated)
}
```

- [ ] **Step 4: Create `target-repo-files/handlers/health.go`**

```
target-repo-files/handlers/health.go
```

```go
package handlers

import "net/http"

func Health(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok"}`))
}
```

- [ ] **Step 5: Create `target-repo-files/README.md`**

```
target-repo-files/README.md
```

```markdown
# User API

A minimal REST API for managing users, backed by PostgreSQL.

## Endpoints

- `GET /health` — health check
- `GET /users` — list all users
- `GET /users/{id}` — get a user by ID
- `POST /users` — create a new user

## Running

```bash
go run .
```

Requires a PostgreSQL database. Set `DATABASE_URL` to configure the connection.
```

- [ ] **Step 6: Commit**

```bash
git add target-repo-files/
git commit -m "feat: add synthetic Go source files for target repo"
```

---

### Task 2: Create the triage guidance skill

**Files:**
- Create: `skill-files/.claude/skills/triage-guidance/SKILL.md`

This file is copied into the target repo between the control and treatment runs.

- [ ] **Step 1: Create `skill-files/.claude/skills/triage-guidance/SKILL.md`**

```
skill-files/.claude/skills/triage-guidance/SKILL.md
```

```markdown
---
name: triage-guidance
description: >-
  Project-specific triage rules for this repository. Use when triaging
  GitHub issues to apply the correct labels and priority.
---

# Triage Guidance

When triaging issues in this repository, apply these rules:

## Labels

- Issues mentioning API routes, HTTP handlers, or endpoints: `area:api`
- Issues mentioning database, queries, or connections: `area:data`
- Issues mentioning configuration or environment variables: `area:config`

## Priority

- Any issue describing a crash, panic, or 500 error: `priority:critical`
- Any issue describing incorrect data or wrong responses: `priority:high`
- Any issue requesting a new feature: `priority:medium`

## Classification

- Issues requesting new endpoints or capabilities: `type:feature`
- Issues describing broken existing behavior: `type:bug`
- Issues about performance degradation: `type:performance`
```

- [ ] **Step 2: Commit**

```bash
git add skill-files/
git commit -m "feat: add triage guidance skill for treatment run"
```

---

### Task 3: Create setup-target-repo.sh

**Files:**
- Create: `setup-target-repo.sh`

This script creates the synthetic GitHub repo, pushes the Go source files, creates labels matching the skill's taxonomy, and files the test issue.

- [ ] **Step 1: Create `setup-target-repo.sh`**

```
setup-target-repo.sh
```

```bash
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
trap "rm -rf ${WORK_DIR}" EXIT

git -C "${WORK_DIR}" init -b main
cp -r "${SCRIPT_DIR}/target-repo-files/"* "${WORK_DIR}/"
mkdir -p "${WORK_DIR}/handlers"
if [[ -d "${SCRIPT_DIR}/target-repo-files/handlers" ]]; then
  cp -r "${SCRIPT_DIR}/target-repo-files/handlers/"* "${WORK_DIR}/handlers/"
fi

git -C "${WORK_DIR}" add -A
git -C "${WORK_DIR}" commit -m "Initial commit: minimal Go REST API"
git -C "${WORK_DIR}" remote add origin "https://github.com/${FULL_REPO}.git"
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x setup-target-repo.sh
```

- [ ] **Step 3: Add `.experiment-state` to `.gitignore`**

Create `.gitignore`:

```
.experiment-state
```

- [ ] **Step 4: Commit**

```bash
git add setup-target-repo.sh .gitignore
git commit -m "feat: add setup-target-repo.sh"
```

---

### Task 4: Create run.sh

**Files:**
- Create: `run.sh`

This is the main experiment runner. It reads state from `setup-target-repo.sh`, runs the control and treatment fullsend triage invocations, and collects results.

**Key details about `fullsend run`:**
- Invoked as: `fullsend run triage --fullsend-dir <path> --target-repo <path>`
- `--fullsend-dir` must point to a directory with `harness/triage.yaml`, `agents/triage.md`, `skills/`, `policies/`, `scripts/`, `env/`
- `--target-repo` is the local path to the cloned target repo
- Output goes to `/tmp/fullsend/agent-triage-<id>/` by default, or `--output-dir <path>`
- Transcripts are extracted to `<output>/iteration-1/transcripts/`
- Agent result JSON is at `<output>/iteration-1/output/agent-result.json`
- Required env vars: `GITHUB_ISSUE_URL`, `GH_TOKEN`, `ANTHROPIC_VERTEX_PROJECT_ID`, `CLOUD_ML_REGION`, `GOOGLE_APPLICATION_CREDENTIALS`

- [ ] **Step 1: Create `run.sh`**

```
run.sh
```

```bash
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
# shellcheck source=/dev/null
source "${STATE_FILE}"
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

# ── Run function ───────────────────────────────────────────────────
run_triage() {
  local label="$1"
  local output_dir="${RESULTS_DIR}/${label}"
  local repo_dir

  step "Running triage (${label})"

  # Clone target repo to a temp dir.
  repo_dir=$(mktemp -d)
  git clone "https://github.com/${FULL_REPO}.git" "${repo_dir}/repo"
  info "Cloned to ${repo_dir}/repo"

  # Run fullsend triage.
  local run_output_dir
  run_output_dir=$(mktemp -d)

  export GITHUB_ISSUE_URL="${ISSUE_URL}"
  export GH_TOKEN="${GH_TOKEN:-$(gh auth token)}"

  fullsend run triage \
    --fullsend-dir "${FULLSEND_DIR}" \
    --target-repo "${repo_dir}/repo" \
    --output-dir "${run_output_dir}" \
    || true

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

  # Clean up temp dirs.
  rm -rf "${repo_dir}" "${run_output_dir}"

  pass "${label} run complete"
}

# ── Control run ────────────────────────────────────────────────────
run_triage "control"

# ── Add skill to target repo ──────────────────────────────────────
step "Adding triage-guidance skill to target repo"
SKILL_WORK_DIR=$(mktemp -d)
git clone "https://github.com/${FULL_REPO}.git" "${SKILL_WORK_DIR}/repo"
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x run.sh
```

- [ ] **Step 3: Commit**

```bash
git add run.sh
git commit -m "feat: add run.sh for control/treatment triage comparison"
```

---

### Task 5: Create README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```
README.md
```

```markdown
# Experiment: Target Repository Skills in Triage

## Hypothesis

When `fullsend run triage` executes Claude inside the target repository
directory, Claude discovers and uses `.claude/skills/` from that repository —
even though `CLAUDE_CONFIG_DIR` is set to `/tmp/claude-config` (the sandbox
config directory for fullsend's own agent and skill definitions).

## Background

Fullsend provisions agents inside OpenShell sandboxes. The bootstrap sequence
sets `CLAUDE_CONFIG_DIR=/tmp/claude-config` where it copies the agent definition
and harness-declared skills. Claude is then invoked with `cd <target-repo-dir>`.

Claude Code discovers project-level skills from `.claude/skills/` in the current
working directory's git root. This experiment tests whether that CWD-based
discovery still works when `CLAUDE_CONFIG_DIR` is overridden.

## Method

- **Independent variable:** Presence of `.claude/skills/triage-guidance/SKILL.md`
  in the target repository.
- **Control:** Triage run against a synthetic Go REST API repo without
  `.claude/skills/`.
- **Treatment:** Same run, same issue, but with a triage guidance skill committed
  to the repo.

All other inputs are held constant: same codebase, same GitHub issue, same
fullsend scaffold (agent, harness, policy, scripts), same model.

### Evidence

1. **JSONL transcript** (primary) — shows whether the skill appears in Claude's
   system prompt.
2. **Triage JSON output** (secondary) — shows whether the agent's labeling
   behavior changed.

## Results

_To be filled after running the experiment._

### Control

_Paste or link to `results/control/agent-result.json` summary._

### Treatment

_Paste or link to `results/treatment/agent-result.json` summary._

### Skill Discovery

_Did `triage-guidance` appear in the treatment transcript's system prompt?_

## Conclusion

_To be filled after analyzing results._

## See Also

- [Design spec](docs/2026-04-28-target-repo-skills-design.md)
- [HOW_TO](HOW_TO.md)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add experiment README"
```

---

### Task 6: Create HOW_TO.md

**Files:**
- Create: `HOW_TO.md`

Follows the experiments repo's HOW_TO skill format: Purpose, Requirements, Steps, Expected Output.

- [ ] **Step 1: Create `HOW_TO.md`**

```
HOW_TO.md
```

```markdown
## Purpose

Run the target-repo-skills experiment to determine whether a target
repository's `.claude/skills/` are discovered by the fullsend triage agent
inside an OpenShell sandbox.

## Requirements

| Requirement | Link |
|-------------|------|
| fullsend CLI | Built from fullsend repo: `go build ./cmd/fullsend` |
| gh CLI | https://cli.github.com/ |
| git | https://git-scm.com/ |
| GCP credentials | `gcloud auth application-default login` |

### Environment variables

| Variable | Description |
|----------|-------------|
| `FULLSEND_DIR` | Path to the fullsend scaffold directory (e.g., `/path/to/fullsend/internal/scaffold/fullsend-repo`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID with Vertex AI access |
| `CLOUD_ML_REGION` | GCP region for Vertex AI (e.g., `us-east5`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account key or ADC file |
| `TARGET_ORG` | (Optional) GitHub org/user for the synthetic repo. Defaults to `maruiz93` |
| `TARGET_REPO` | (Optional) Repo name. Defaults to `experiment-target-repo-skills` |

## Steps

1. Navigate to the experiment directory:
   ```bash
   cd target-repo-skills
   ```

2. Set required environment variables:
   ```bash
   export FULLSEND_DIR=/path/to/fullsend/internal/scaffold/fullsend-repo
   export ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
   export CLOUD_ML_REGION=us-east5
   export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
   ```

3. Create the synthetic target repo and file the test issue:
   ```bash
   ./setup-target-repo.sh
   ```

4. Run the experiment:
   ```bash
   ./run.sh
   ```

## Expected Output

- `results/control/agent-result.json` — triage output without the skill
- `results/control/transcript.jsonl` — Claude session transcript without the skill
- `results/treatment/agent-result.json` — triage output with the skill
- `results/treatment/transcript.jsonl` — Claude session transcript with the skill
- The treatment transcript should contain `triage-guidance` in the system prompt
  if skill discovery works
- The treatment `agent-result.json` should use labels from the skill's taxonomy
  (`area:api`, `priority:critical`, `type:bug`)
```

- [ ] **Step 2: Commit**

```bash
git add HOW_TO.md
git commit -m "docs: add HOW_TO for experiment reproduction"
```

---

### Task 7: Add results/.gitkeep and final commit

**Files:**
- Create: `results/control/.gitkeep`
- Create: `results/treatment/.gitkeep`

- [ ] **Step 1: Create .gitkeep files**

```bash
touch results/control/.gitkeep results/treatment/.gitkeep
```

- [ ] **Step 2: Update .gitignore to exclude result artifacts but keep directory structure**

Append to `.gitignore`:

```
.experiment-state
results/control/*.json
results/control/*.jsonl
results/treatment/*.json
results/treatment/*.jsonl
```

- [ ] **Step 3: Commit**

```bash
git add results/ .gitignore
git commit -m "chore: add results directory structure"
```
