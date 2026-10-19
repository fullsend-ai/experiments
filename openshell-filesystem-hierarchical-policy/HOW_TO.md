# HOW TO: OpenShell Filesystem Hierarchical Policy

## Purpose

Reproduce the Landlock hierarchical filesystem policy experiment
that tests whether a `read_only` subdirectory inside a `read_write`
parent is correctly enforced as read-only by OpenShell.

## Requirements

| Requirement                 | Link                                                       |
|-----------------------------|------------------------------------------------------------|
| OpenShell CLI               | <https://docs.openshell.dev/getting-started/installation/> |
| Docker                      | <https://docs.docker.com/get-docker/>                      |
| Python 3                    | <https://www.python.org/downloads/>                        |
| GitHub CLI (repo mode only) | <https://cli.github.com/>                                  |

## Steps

1. Start the OpenShell gateway if it is not already running:

   ```bash
   openshell gateway start
   ```

2. Navigate to the experiment directory:

   ```bash
   cd openshell-filesystem-hierarchical-policy
   ```

3. Run with synthetic fixtures (no external dependencies):

   ```bash
   ./run.sh
   ```

   Or, to test against a real GitHub repo:

   ```bash
   ./run.sh --repo octocat/Hello-World
   ```

   The `--repo` flag requires `gh` to be installed and authenticated.

## Expected Output

- Terminal prints a table of 24 test assertions with pass/fail indicators

  ```text
  ID   CAT      OP                 PATH                      EXPECT   RESULT
  1.3  overlap  write              …/target-repo/README.md   EACCES   EACCES
  ```

- Summary line shows total passed and failed counts
- `results/` directory is created containing:
  - `probe-output.jsonl` — one JSON object per test assertion
  - `sandbox-logs.txt` — sandbox container logs
- Exit code is 0 if all 24 assertions pass, nonzero otherwise
