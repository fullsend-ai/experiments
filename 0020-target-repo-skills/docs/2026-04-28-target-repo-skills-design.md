# Experiment: Target Repository Skills in Triage

## Hypothesis

When `fullsend run --agent triage` executes Claude inside the target repository
directory, Claude discovers and uses `.claude/skills/` from that repository —
even though `CLAUDE_CONFIG_DIR` is set to `/tmp/claude-config` (the sandbox
config directory for fullsend's own agent and skill definitions).

## Background

Fullsend provisions agents inside OpenShell sandboxes. The bootstrap sequence
(`internal/cli/run.go:532-588`) sets up `CLAUDE_CONFIG_DIR=/tmp/claude-config`
where it copies the agent definition and harness-declared skills. Claude is then
invoked with `cd <target-repo-dir> && source .env && claude --agent ...`
(line 774).

When `CLAUDE_CONFIG_DIR` is set, Claude uses it instead of `~/.claude/` for
user-level configuration. However, Claude Code also discovers project-level
skills from `.claude/skills/` in the current working directory's git root. The
question is whether this CWD-based discovery still works when `CLAUDE_CONFIG_DIR`
is overridden.

## Method

### Independent variable

Presence of `.claude/skills/triage-guidance/SKILL.md` in the target repository.

### Controlled variables (held constant)

- Target repository codebase (synthetic Go REST API)
- GitHub issue text (identical issue for both runs)
- Triage agent definition (`internal/scaffold/fullsend-repo/agents/triage.md`)
- Triage harness (`internal/scaffold/fullsend-repo/harness/triage.yaml`)
- Triage policy (`internal/scaffold/fullsend-repo/policies/triage.yaml`)
- Pre/post scripts from the scaffold
- Model (opus)

### Dependent variables

1. **JSONL transcript** — the primary evidence. Claude Code writes session
   transcripts to `$CLAUDE_CONFIG_DIR/*.jsonl`. The `system` messages in this
   log show exactly which skills were loaded into the agent's context. If the
   target repo's `triage-guidance` skill appears in the system prompt, that
   proves discovery. If the agent's reasoning references the skill's rules,
   that proves usage.
2. **Triage JSON output** — secondary confirmation. Labels, priority, and
   reasoning text in the structured output show behavioral impact.

### Runs

1. **Control:** `fullsend run --agent triage` against the target repo without
   `.claude/skills/`.
2. **Treatment:** Same command, same issue, but `.claude/skills/triage-guidance/SKILL.md`
   has been committed and pushed to the target repo.

## Synthetic Target Repository

A minimal Go REST API project created by `setup-target-repo.sh`:

```
experiment-target-repo-skills/
├── go.mod
├── main.go                # HTTP server entry point
├── handlers/
│   ├── users.go           # CRUD handlers
│   └── health.go          # Health check endpoint
└── README.md
```

### Triage guidance skill

Added to the target repo between the control and treatment runs as
`.claude/skills/triage-guidance/SKILL.md`:

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

### GitHub issue

Filed via `setup-target-repo.sh`:

- **Title:** `/users` endpoint returns 500 when database is unreachable
- **Body:** When the PostgreSQL connection drops, hitting `GET /users` returns a
  500 Internal Server Error with a panic in the logs. Expected behavior: return
  503 Service Unavailable with an appropriate error message.

This issue deliberately spans two areas (API and data) and describes a panic,
triggering the `priority:critical` rule. The control run has no guidance on
these labels, so any alignment with the skill's taxonomy in the treatment run
is signal that the skill was discovered.

## Experiment Directory Structure

```
target-repo-skills/
├── README.md                        # Hypothesis, method, results
├── HOW_TO.md                        # Reproduction steps
├── setup-target-repo.sh             # Creates synthetic GitHub repo + files issue
├── run.sh                           # Runs control and treatment, captures output
├── docs/
│   └── 2026-04-28-target-repo-skills-design.md   # This file
└── results/
    ├── control/                     # Without .claude/skills/
    │   ├── agent-result.json        # Triage JSON output
    │   └── transcript.jsonl         # Claude session transcript
    └── treatment/                   # With .claude/skills/
        ├── agent-result.json
        └── transcript.jsonl
```

## Run Flow

### setup-target-repo.sh

Accepts `TARGET_ORG` env var (defaults to `maruiz93`) and
`TARGET_REPO` (defaults to `experiment-target-repo-skills`).

1. Create GitHub repo `$TARGET_ORG/$TARGET_REPO` via `gh repo create`.
2. Commit and push the Go source files (go.mod, main.go, handlers/, README.md).
3. Create labels on the repo matching the skill's taxonomy (`area:api`,
   `area:data`, `area:config`, `priority:critical`, `priority:high`,
   `priority:medium`, `type:feature`, `type:bug`, `type:performance`) so the
   triage agent can apply them.
4. File the GitHub issue via `gh issue create`.
5. Do NOT add `.claude/skills/` — this is the control state.

### run.sh

1. **Control run:** `fullsend run --agent triage --repo $TARGET_ORG/$TARGET_REPO --issue <number>`.
   Save output JSON and JSONL transcript to `results/control/`.
2. **Add skill:** Clone the target repo to a temp directory, add
   `.claude/skills/triage-guidance/SKILL.md`, commit, and push.
3. **Treatment run:** Same command, same issue.
   Save output JSON and JSONL transcript to `results/treatment/`.

Both runs capture the JSONL transcript extracted from the sandbox. The
transcript is the primary evidence — it shows whether Claude's system prompt
included the target repo skill.

## Success Criteria

Evidence is evaluated at two levels:

### Primary: JSONL transcript (skill discovery)

- **Positive:** The treatment JSONL shows `triage-guidance` in the system prompt
  skill list. The control JSONL does not.
- **Negative:** Neither JSONL mentions the skill — `CLAUDE_CONFIG_DIR` prevents
  CWD-based skill discovery, and fullsend would need code changes (e.g.,
  scanning the target repo's `.claude/skills/` in `bootstrapSandbox()`) to
  support target repo skills.

### Secondary: Triage JSON output (skill usage)

- **Positive:** Treatment output uses the skill's label taxonomy (`area:api`,
  `area:data`, `priority:critical`, `type:bug`) and/or references its rules in
  reasoning. Control output does not use these specific labels.
- **Inconclusive:** Treatment uses similar labels but not clearly attributable
  to the skill. Would require a more distinctive skill taxonomy to retest.

Both positive and negative outcomes are valuable. A negative result identifies
the exact code change needed in fullsend.

## Security Considerations

Target repo skills are user-controlled content. If this experiment shows that
skills are discovered, follow-up work should evaluate:

- Whether `.claude/skills/` should be scanned by `fullsend scan context` before
  the agent runs (prompt injection risk).
- Whether skill discovery from target repos should be opt-in via harness config.
- Whether `.claude/` should be added to the protected paths list in
  `post-review.sh` (it already is: `.claude/` is listed).
