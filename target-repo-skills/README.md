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