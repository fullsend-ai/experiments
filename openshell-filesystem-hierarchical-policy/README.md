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

Place the results after running in "./findings.md", using the following
format

````markdown
## Assertion summary

| Cat     | Tests | Passed | Failed |
|---------|-------|--------|--------|
| overlap | 7     |        |        |
| rw      | 4     |        |        |
| ro      | 6     |        |        |
| deny    | 4     |        |        |
| edge    | 3     |        |        |
| Total   | 24    |        |        |

## Hypothesis outcomes

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
