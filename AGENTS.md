# AGENTS.md

This repository holds experiments for the fullsend platform. Each experiment tests a hypothesis about autonomous agent infrastructure, security, tooling, or workflows. Experiments are self-contained directories (or standalone `.md` files) with structured metadata.

## How to work in this repo

### Experiment conventions

Experiments follow a numbered directory convention modeled after [ADRs in fullsend](https://github.com/fullsend-ai/fullsend/tree/main/docs/ADRs).

**Directory naming:** `NNNN-short-description/` (zero-padded 4-digit number). Single-file experiments use `NNNN-short-description.md`. The template at `0000-experiment-template/` is excluded from lint checks.

**Frontmatter:** Every experiment's `README.md` (or standalone `.md`) must include YAML frontmatter with at minimum `title` and `status`:

```yaml
---
title: "NNNN. Short description"
status: Active
topics:
  - topic-tag
---
```

**Valid statuses:**
- **Active** — experiment is in progress or being iterated on
- **Concluded** — experiment finished, results documented, no further work planned
- **Abandoned** — experiment stopped before completion (document why)
- **Merged** — experiment results were adopted into the main project (link to ADR/PR)

**Topics:** Optional list of tags for categorization (e.g., `security`, `reliability`, `tooling`).

**Creating a new experiment:** Copy `0000-experiment-template/README.md`, assign the next available number, and fill in the sections. Always check existing numbers first (`ls -d [0-9]*`) to avoid collisions. After creating the experiment, add it to the index table in the root `README.md`.

**README index:** The root `README.md` contains a table listing every experiment with its number, name, and status. Keep this table in sync — add a row when creating an experiment, update the status when it changes, and remove the row if the experiment is deleted.

### Linting

Pre-commit hooks enforce experiment conventions. Always stage your changes before running `pre-commit run` — hooks only check staged files.

| Hook | What it validates |
|------|-------------------|
| `lint-experiment-numbers` | Filenames match `^[0-9]{4}-`, no duplicate numbers, no leading zeros in titles |
| `lint-experiment-frontmatter` | Required fields (`title`, `status`), valid status values, `topics` is a list |
| `lint-experiment-index` | README.md index table lists every experiment on disk and vice versa |

Run all hooks manually: `pre-commit run --all-files`

### Commit message format

Use [Conventional Commits](https://www.conventionalcommits.org/). The commit subject must start with a type prefix followed by an optional scope and colon:

```
<type>(<scope>): <short description>
```

Common types: `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`.

Use the experiment number as scope when the change is scoped to a single experiment:

```
docs(0003): add results from fire drill week 2
feat(0024): add new experiment for sandbox networking
```

### DCO sign-off

This repository requires a [Developer Certificate of Origin (DCO)](https://developercertificate.org/). Human-proposed commits **must** be signed off: use `git commit -s`. Human-driven agent sessions (e.g., using Claude Code locally) should also sign off. **Autonomous agent commits are exempt** and must never supply `-s` or `Signed-off-by`.

### General rules

- Do not commit secrets (tokens, API keys, credentials) or sensitive data (GCP project names, service account identifiers, internal hostnames). Use environment variables with no defaults for sensitive values.
- Keep experiments self-contained. Cross-references between experiments are fine, but one experiment should not depend on another's runtime artifacts.
- When an experiment concludes, update its status to `Concluded` (or `Abandoned`/`Merged`) and document results in a `RESULTS.md` or in the Results section of `README.md`.

## Think before acting

State your assumptions explicitly before writing code. When the issue description is ambiguous, present competing interpretations and choose the most conservative one. If you cannot determine the correct behavior from the code and context, stop — do not guess.

## Simplicity first

Write only the code required to satisfy the issue. Do not add speculative features, abstractions for single-use code paths, or error handling for scenarios that cannot occur.

## Surgical changes

Modify only what the issue authorizes. Do not refactor adjacent code, fix unrelated style issues, or improve comments on lines you did not change. Match the existing style of the file.
