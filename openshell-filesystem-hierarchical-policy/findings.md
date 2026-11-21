# Filesystem Hierarchical Policy Experiment — Findings

## Experiment overview

This experiment tests whether OpenShell's Landlock-based filesystem
policy enforces hierarchical path precedence: when a subdirectory is
marked `read_only` inside a parent marked `read_write`, does the
more-specific restriction win?

The policy under test marks `/sandbox` as `read_write` and
`/sandbox/workspace/target-repo/` as `read_only`, with
`include_workdir: false` to prevent OpenShell from silently adding
the working directory to `read_write`.

24 assertions across five categories (overlap, read-write, read-only,
deny, edge cases) probe the policy boundary.

## Execution

```bash
./run.sh
```

Ran with synthetic fixtures (no `--repo` flag). The orchestrator
created a sandbox with the test policy, seeded a
`target-repo/README.md`, uploaded `probe.py`, and collected JSONL
results.

## Results

20 of 24 assertions passed. **4 failures, all in the overlap
category:**

**Overlap** (target-repo is ro child of rw /sandbox):

| ID  | Op      | Path             | Expect | Got    |
| --- | ------- | ---------------- | ------ | ------ |
| 1.1 | read    | …/README.md      | ok     | ok     |
| 1.2 | listdir | …/target-repo/   | ok     | ok     |
| 1.3 | write   | …/README.md      | EACCES | **ok** |
| 1.4 | create  | …/new-file.txt   | EACCES | **ok** |
| 1.5 | mkdir   | …/newdir/        | EACCES | **ok** |
| 1.6 | write   | …/other/file.txt | ok     | ok     |
| 1.7 | write   | …/workspace/file | ok     | ok     |

**Read-write:**

| ID  | Op         | Path             | Expect | Got |
| --- | ---------- | ---------------- | ------ | --- |
| 2.1 | write+read | /sandbox/test-rw | ok     | ok  |
| 2.2 | write+read | /tmp/test-rw     | ok     | ok  |
| 2.3 | write      | /dev/null        | ok     | ok  |
| 2.4 | mkdir      | /sandbox/newdir/ | ok     | ok  |

**Read-only:**

| ID  | Op    | Path              | Expect | Got    |
| --- | ----- | ----------------- | ------ | ------ |
| 3.1 | read  | /usr/bin/ls       | ok     | ok     |
| 3.2 | write | /usr/test-write   | EACCES | EACCES |
| 3.3 | read  | /etc/hostname     | ok     | ok     |
| 3.4 | write | /etc/test-write   | EACCES | EACCES |
| 3.5 | read  | /proc/self/status | ok     | ok     |
| 3.6 | read  | /dev/urandom      | ok     | ok     |

**Deny (unlisted paths):**

| ID  | Op    | Path            | Expect | Got    |
| --- | ----- | --------------- | ------ | ------ |
| 4.1 | read  | /home/          | EACCES | EACCES |
| 4.2 | read  | /root/          | EACCES | EACCES |
| 4.3 | read  | /opt/           | EACCES | EACCES |
| 4.4 | write | /opt/test-write | EACCES | EACCES |

**Edge cases:**

| ID  | Op        | Path                  | Expect | Got    |
| --- | --------- | --------------------- | ------ | ------ |
| 5.1 | symlink   | /tmp/link→/etc/passwd | EACCES | EACCES |
| 5.2 | traversal | …/repo/../other/file  | ok     | ok     |
| 5.3 | delete    | …/README.md           | EACCES | **ok** |

Raw data: [results/probe-output.jsonl](results/probe-output.jsonl)

### Assertion summary

| Category  | Tests  | Passed | Failed |
| --------- | ------ | ------ | ------ |
| overlap   | 7      | 4      | 3      |
| rw        | 4      | 4      | 0      |
| ro        | 6      | 6      | 0      |
| deny      | 4      | 4      | 0      |
| edge      | 3      | 2      | 1      |
| **Total** | **24** | **20** | **4**  |

### Hypothesis outcomes

| ID | Status      | Hypothesis                         |
| -- | ----------- | ---------------------------------- |
| H0 | **REFUTED** | Overlap: specific path wins        |
| H1 | Confirmed   | Unlisted paths inaccessible        |
| H2 | Confirmed   | Read-only: reads ok, writes fail   |
| H3 | Confirmed   | Read-write: both ops work          |
| H4 | Confirmed   | Symlinks resolved before policy    |
| H5 | Confirmed   | Traversal resolved before policy   |
| H6 | Confirmed   | `include_workdir: false` honored   |
| H7 | Confirmed   | Runs on Fedora 44                  |

**H0 detail:** Tests 1.3, 1.4, 1.5 all returned `ok` — the
`read_write` parent grant is not overridden by a more-specific
`read_only` child. See analysis below.

## Key finding: Landlock unions permissions, it does not override

The headline result is that **H0 is refuted**. When both
`/sandbox` (read\_write) and `/sandbox/workspace/target-repo/`
(read\_only) appear in the policy, the child path is writable.

This is not a bug — it is how Landlock works. Landlock rules are
**additive**: a rule on a path grants permissions to that path and
all its descendants. When a parent path grants `read + write`, that
grant propagates to every child path. A separate `read_only` rule
on a child path adds `read` access (which the parent already
granted), but it cannot revoke the `write` access granted by the
parent.

In Landlock's permission model:

- A ruleset declares which access rights it **handles** (restricts)
- For each handled right, access is denied unless at least one rule
  grants it
- Rules are per-path and apply to the path **and all descendants**
- Multiple rules on overlapping paths are **unioned**, not
  overridden

So `target-repo` gets: `read + write` (from `/sandbox` rule)
**union** `read` (from `/sandbox/workspace/target-repo/` rule) =
`read + write`. The `read_only` intent is lost.

### Sandbox logs confirm the mechanism

From `results/sandbox-logs.txt`:

```text
CONFIG:PROBED [INFO] Landlock filesystem sandbox available
  [abi:v8 compat:BestEffort ro:8 rw:3]
CONFIG:APPLYING [INFO] Applying Landlock filesystem sandbox
  [abi:V2 compat:BestEffort ro:8 rw:3]
CONFIG:BUILT [INFO] Landlock ruleset built
  [rules_applied:9 skipped:2]
```

- Landlock ABI v8 is available on this kernel, but OpenShell applies
  rules using **ABI V2** with `BestEffort` compatibility
- 8 read-only + 3 read-write = 11 rules declared, but only 9
  applied and **2 were skipped** — OpenShell silently drops rules
  it cannot map to the Landlock ABI version it uses
- The ABI downgrade may explain why `read_only` within `read_write`
  is not enforced, but the more likely explanation is the additive
  permission model described above — this is fundamental to
  Landlock's design, not an ABI limitation

### Test 5.3 failure confirms the same root cause

Test 5.3 (delete `target-repo/README.md`) also failed: `unlink`
requires write permission on the parent directory, and the parent
directory inherits write from `/sandbox`. This is consistent with
the overlap behavior, not a separate bug.

## Conclusions

### What works

OpenShell's Landlock integration correctly enforces:

- **Non-overlapping read-only paths** (H2): `/usr`, `/etc`,
  `/proc`, `/dev/urandom` are all properly read-only
- **Read-write paths** (H3): `/sandbox`, `/tmp`, `/dev/null`
  allow both operations
- **Deny-by-default** (H1): unlisted paths (`/home`, `/root`,
  `/opt`) are inaccessible
- **Symlink resolution** (H4): writing through a symlink to a
  protected path is blocked
- **Traversal resolution** (H5): `..` is resolved before policy
  evaluation
- **Fedora 44 compatibility** (H7): kernel 7.0.x with Landlock v8

### What does not work

**Hierarchical path restriction is not possible with the current
policy model.** You cannot mark a subdirectory as `read_only` inside
a `read_write` parent and expect the restriction to hold. Landlock's
additive permission model means the parent's `read_write` grant
propagates to all descendants regardless of child rules.

### Implications for OpenShell policy design

The `read_only` / `read_write` distinction in OpenShell's policy
YAML implies hierarchical override semantics that Landlock does not
provide. This creates a gap between user intent and enforcement:

- A policy author writing `read_only: [/sandbox/workspace/repo/]`
  alongside `read_write: [/sandbox]` reasonably expects the repo to
  be read-only
- Landlock silently ignores the intent and makes the repo writable
- No warning is emitted — the `rules_applied` log does not flag the
  semantic conflict

### Recommendations

1. **OpenShell should warn on overlapping paths.** When a
   `read_only` path is a descendant of a `read_write` path, the
   policy validator should emit a warning that the `read_only`
   restriction will not be enforced.

2. **Restructure policies to avoid overlap.** Instead of marking a
   subdirectory `read_only` inside a `read_write` parent, list the
   writable siblings explicitly:

   ```yaml
   # BROKEN — read_only inside read_write is not enforced
   read_only:
     - /sandbox/workspace/target-repo/
   read_write:
     - /sandbox

   # WORKING — enumerate writable paths, exclude the repo
   read_only:
     - /sandbox/workspace/target-repo/
   read_write:
     - /sandbox/workspace/other-project/
     - /sandbox/workspace/scratch/
     - /tmp
   ```

   The trade-off: every new writable path must be explicitly listed,
   which is more verbose but matches Landlock's actual enforcement.

3. **Investigate ABI V2 downgrade.** Kernel 7.0 provides Landlock
   ABI v8, but OpenShell applies rules at V2. Later ABI versions
   may offer features relevant to path restriction granularity.
   The 2 skipped rules should be investigated to determine what
   policy intent is being silently dropped.

## Environment

- **OpenShell version:** 0.17.x (from gateway logs)
- **Kernel:** 7.0.12-201.fc44.x86_64
- **Landlock ABI:** v8 available, V2 applied (BestEffort)
- **OS:** Fedora 44
- **Date:** 2026-06-17
