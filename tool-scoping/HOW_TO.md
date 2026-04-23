# How to Reproduce

## Purpose

Reproduce the tool scoping experiment results that support
[ADR 0022](https://github.com/fullsend-ai/fullsend-adr-tools/blob/main/docs/ADRs/0022-allowed-and-disallowed-tools-for-agents.md).

## Requirements

| Requirement | Link |
|-------------|------|
| Claude CLI | https://docs.anthropic.com/en/docs/claude-code/overview |
| git | https://git-scm.com/downloads |
| Python 3 | https://www.python.org/downloads/ |

Claude CLI must be authenticated (`claude --version` should succeed).
Python 3 is used to generate `results/summary.yaml` from raw JSON output.

## Steps

1. Navigate to the experiment directory:
   ```bash
   cd experiments/adr0022-tool-scoping
   ```

2. Run all tests:
   ```bash
   ./run.sh
   ```

   Or run a specific test group:
   ```bash
   ./run.sh frontmatter  # tools/disallowedTools in --agent vs subagent
   ./run.sh deny         # permissions.deny enforcement
   ./run.sh allow        # permissions.allow with dontAsk
   ./run.sh bypass       # bypassPermissions behavior
   ```

3. Review the summary:
   ```bash
   cat results/summary.yaml
   ```

   For full detail on a specific test, check its JSON file:
   ```bash
   cat results/frontmatter-tools-bash-skip.json | python3 -m json.tool
   ```

## Expected Output

- `results/` directory contains one JSON file per test (12 total) plus
  `summary.yaml`
- `summary.yaml` shows each test's result and permission denials in a
  scannable format
- Tests matching the findings in [README.md](README.md):
  - `frontmatter-*` tests: `tools`/`disallowedTools` have no effect in
    `--agent` sessions (no denials), but work for subagents
  - `permissions-deny`: `echo hello` succeeds, `ls /tmp` denied
  - `permissions-allow`: `echo hello` succeeds, `ls /tmp` denied
  - `bypass-no-tools-write`: Write denied (no permission_denials or Write
    in denials)
  - `bypass-allow-write`: Write succeeds
- Expect ~30-60 seconds per test, ~10 minutes total