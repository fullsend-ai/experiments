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

### Control

- **Severity:** high
- **Labels:** none (no skill-specific labels referenced)
- **Overall clarity score:** 0.89
- Full output: [`results/control/agent-result.json`](results/control/agent-result.json)

### Treatment

- **Severity:** critical
- **Labels:** `area:api`, `area:data`, `priority:critical`, `type:bug`
- **Overall clarity score:** 0.90
- Reasoning explicitly cites: _"Per triage guidance"_
- Full output: [`results/treatment/agent-result.json`](results/treatment/agent-result.json)

### Skill Discovery

**Yes.** The treatment transcript shows 3 mentions of `triage-guidance`:

1. The agent called `Skill("triage-guidance")` during triage.
2. The skill content was loaded from `/tmp/workspace/repo/.claude/skills/triage-guidance`.
3. The skill instructions appeared in the agent's context.

The control transcript contains 0 mentions of `triage-guidance`.

```bash
$ grep -c 'triage-guidance' results/treatment/transcript.jsonl
3
$ grep -c 'triage-guidance' results/control/transcript.jsonl
0
```

## Conclusion

**Hypothesis confirmed.** Target repository `.claude/skills/` are discovered and
used by the fullsend triage agent inside OpenShell sandboxes, even though
`CLAUDE_CONFIG_DIR` is overridden to `/tmp/claude-config`.

Claude Code's CWD-based project skill discovery (`cd <target-repo> && claude`)
operates independently of `CLAUDE_CONFIG_DIR`. The agent discovers skills from
the git root of its working directory regardless of where user-level config
points.

**Behavioral impact:** The triage guidance skill changed the agent's output in
two measurable ways:

1. **Severity escalation:** "high" → "critical" (matching the skill's rule that
   panic/500 errors are `priority:critical`)
2. **Structured labeling:** The treatment output includes explicit label
   references (`area:api`, `area:data`, `priority:critical`, `type:bug`) that
   match the skill's taxonomy exactly

The triage agent comments (control and treatment) can be seen on the target
repo issue: https://github.com/maruiz93/experiment-target-repo-skills/issues/1

## See Also

- [Design spec](docs/2026-04-28-target-repo-skills-design.md)
- [HOW_TO](HOW_TO.md)