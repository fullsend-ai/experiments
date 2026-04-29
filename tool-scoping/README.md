# ADR 0022 Tool Scoping Experiment

Evidence for
[ADR 0022](https://github.com/fullsend-ai/fullsend-adr-tools/blob/main/docs/ADRs/0022-allowed-and-disallowed-tools-for-agents.md).
Tests how Claude Code enforces tool restrictions when agents are launched
with `claude --agent`.

## Summary

| Mechanism | Parameterized? | `--agent` session | Subagent |
|-----------|---------------|-------------------|----------|
| `tools` in frontmatter | No | **No effect** | Restricts to listed tools |
| `disallowedTools` in frontmatter | No | **No effect** | Removes listed tools |
| `permissions.allow` in settings.json | **Yes** | **Enforced** (with `dontAsk`) | — |
| `permissions.deny` in settings.json | **Yes** | **Enforced** (even with `--dangerously-skip-permissions`) | — |
| `bypassPermissions` mode | N/A | **Partial** — auto-approves some tools, denies others | — |

## 1. Frontmatter scoping (`tools`, `disallowedTools`)

`tools` and `disallowedTools` in agent frontmatter **have no effect in
`--agent` sessions**. They only work when the agent runs as a subagent
spawned via the Agent tool.

### `--agent` sessions: `tools` neither restricts nor grants

| Test | Agent config | Action | Result | Evidence |
|------|-------------|--------|--------|----------|
| tools-bash-skip | `tools: Bash` + `--dangerously-skip-permissions` | Write file | **Succeeded** | `tools` didn't block Write |
| tools-write-try-bash | `tools: Write` + `bypassPermissions` | Run `echo hello` via Bash | **Succeeded** | `tools` didn't block Bash |
| tools-write-try-write | `tools: Write` + `bypassPermissions` | Write file | **Denied** | `tools` didn't grant Write (denied by `bypassPermissions`) |
| tools-bash-allow-write | `tools: Bash` + `bypassPermissions` + `allow: Write(*)` | Write file | **Succeeded** | `tools` didn't block Write when `permissions.allow` set |

Agents: [tools-bash-skip.md](agents/tools-bash-skip.md),
[tools-write.md](agents/tools-write.md),
[tools-bash.md](agents/tools-bash.md)
Results: [frontmatter-tools-bash-skip.json](results/frontmatter-tools-bash-skip.json),
[frontmatter-tools-write-try-bash.json](results/frontmatter-tools-write-try-bash.json),
[frontmatter-tools-write-try-write.json](results/frontmatter-tools-write-try-write.json),
[frontmatter-tools-bash-allow-write.json](results/frontmatter-tools-bash-allow-write.json)

### `--agent` sessions: `disallowedTools` has no effect

| Test | Agent config | Action | Result | Evidence |
|------|-------------|--------|--------|----------|
| disallowed-bash | `disallowedTools: Bash` + `--dangerously-skip-permissions` | Run `echo hello` | **Succeeded** | `disallowedTools` didn't remove Bash |

Agent: [disallowed-bash.md](agents/disallowed-bash.md)
Result: [frontmatter-disallowed-bash.json](results/frontmatter-disallowed-bash.json)

### Subagents: both mechanisms work

| Test | Subagent config | Action | Result | Evidence |
|------|----------------|--------|--------|----------|
| subagent-disallowed-bash | `disallowedTools: Bash` | Run `echo hello` | **Denied** — Bash not available | `disallowedTools` works for subagents |
| subagent-tools-bash | `tools: Bash` | Write file | **Denied** — Write not available | `tools` works for subagents |

Agents: [coordinator-disallowed.md](agents/coordinator-disallowed.md) +
[subagent-disallowed-bash.md](agents/subagent-disallowed-bash.md),
[coordinator-tools.md](agents/coordinator-tools.md) +
[subagent-tools-bash.md](agents/subagent-tools-bash.md)
Results: [subagent-disallowed-bash.json](results/subagent-disallowed-bash.json),
[subagent-tools-bash.json](results/subagent-tools-bash.json)

## 2. `permissions.deny` with `--dangerously-skip-permissions`

`permissions.deny` in `.claude/settings.json` **hard-blocks matching
patterns even with `--dangerously-skip-permissions`**.

| Test | Config | `echo hello` | `ls /tmp` |
|------|--------|-------------|-----------|
| permissions-deny | `--dangerously-skip-permissions` + `deny: Bash(ls *)` | **Succeeded** | **Denied** |

Agent: [deny-test.md](agents/deny-test.md)
Settings: [deny-bash-ls.json](settings/deny-bash-ls.json)
Result: [permissions-deny.json](results/permissions-deny.json)

## 3. `permissions.allow` with `dontAsk`

`permissions.allow` in `.claude/settings.json` combined with
`permissionMode: dontAsk` **enforces parameterized patterns** — only
matching tool calls are auto-approved, everything else is auto-denied.

| Test | Config | `echo hello` | `ls /tmp` |
|------|--------|-------------|-----------|
| permissions-allow | `dontAsk` + `allow: Bash(echo *)` | **Succeeded** | **Denied** |

Agent: [dontask.md](agents/dontask.md)
Settings: [allow-bash-echo.json](settings/allow-bash-echo.json)
Result: [permissions-allow.json](results/permissions-allow.json)

## 4. `bypassPermissions` partial bypass

`permissionMode: bypassPermissions` **auto-approves some tools but not
others**. Bash is auto-approved; Write is denied unless supplemented by
`permissions.allow`.

| Test | Config | Write | Evidence |
|------|--------|-------|----------|
| bypass-no-tools-write | `bypassPermissions` (no tools) | **Denied** | `bypassPermissions` doesn't auto-approve Write |
| bypass-allow-write | `bypassPermissions` + `allow: Write(*)` | **Succeeded** | `permissions.allow` supplements `bypassPermissions` |

Agent: [bypass-no-tools.md](agents/bypass-no-tools.md)
Settings: [allow-write.json](settings/allow-write.json)
Results: [bypass-no-tools-write.json](results/bypass-no-tools-write.json),
[bypass-allow-write.json](results/bypass-allow-write.json)

## How to reproduce

See [HOW_TO.md](HOW_TO.md).

## Environment

- **Claude CLI version:** 2.1.118
- **Date:** 2026-04-23
- **OS:** Linux 6.19.11-200.fc43.x86_64 (Fedora 43)