# OpenShell filesystem policy test

**Date:** 2026-06-12
**Status:** Draft

## Goal

Validate that OpenShell's Landlock-based filesystem policy correctly
enforces read\_only/read\_write path restrictions, with a primary
focus on **overlap behavior**: a subdirectory marked `read_only`
inside a parent marked `read_write` should be read-only.

## Policy under test

```yaml
version: 1

filesystem_policy:
  include_workdir: false
  read_only:
    - /usr
    - /lib
    - /proc
    - /dev/urandom
    - /app
    - /etc
    - /var/log
    - /sandbox/workspace/target-repo/
  read_write:
    - /sandbox
    - /tmp
    - /dev/null
```

`include_workdir` must be explicitly set to `false` — it defaults
to `true` throughout the OpenShell implementation and would silently
add the sandbox's working directory to `read_write`, potentially
masking the overlap behavior under test.

## Architecture

```text
experiments/openshell-filesystem-policy/
├── run.sh         # Bash orchestrator (host-side)
├── probe.py       # Python test runner (inside sandbox)
├── policy.yaml    # Policy under test
├── README.md      # Hypotheses, instructions, results
└── results/       # Output directory (.gitignored)
    ├── probe-output.jsonl
    └── sandbox-logs.txt
```

### run.sh (orchestrator)

Host-side bash script following the pattern established in
`experiments/openshell-policy-bypass/run.sh`:

1. Check prerequisites (`openshell` CLI, gateway running)
2. Create sandbox with `--policy policy.yaml --keep
   --no-tty --from base`
3. Connect via SSH (poll for readiness)
4. Seed fixtures (mkdir, write test files; optionally
   clone a real repo if `--repo` flag provided)
5. SCP `probe.py` into `/sandbox/probe.py`
6. Execute: `ssh ... python3 /sandbox/probe.py`
7. Parse JSONL output, print summary table by category
8. Collect sandbox logs via `openshell logs`
9. Delete sandbox
10. Exit nonzero if any assertion failed

### probe.py (runs inside sandbox)

Python script executing inside the sandbox. Each test
attempts one filesystem operation, captures the result and
`errno` on failure, and emits a JSON line.

Output format (one JSON object per line):

```json
{"id":"1.3","cat":"overlap","op":"write","path":"/sandbox/workspace/target-repo/README.md","expect":"EACCES","actual":"EACCES","pass":true}
```

Fields:

- `id`: test number from the matrix
- `cat`: category (overlap, rw, ro, deny, edge)
- `op`: operation attempted
- `path`: filesystem path tested
- `expect`: expected outcome ("ok" or errno name)
- `actual`: actual outcome
- `pass`: boolean
- `detail`: optional context on failure

The probe always exits 0 so the orchestrator can parse
results even when assertions fail.

Errno values that distinguish policy enforcement from
other failures:

- EACCES (13): permission denied — Landlock blocked it
- EPERM (1): operation not permitted — also a policy denial
- ENOENT (2): path doesn't exist — not a policy block
  (indicates a fixture setup problem)

## Test matrix

24 assertions across five categories.

### Category 1 — Overlap (primary focus, 7 tests)

- **1.1** Read file
  `…/target-repo/README.md` → ok
- **1.2** List directory
  `…/target-repo/` → ok
- **1.3** Write file
  `…/target-repo/README.md` → EACCES
  *Headline test — write blocked despite parent rw*
- **1.4** Create new file
  `…/target-repo/new-file.txt` → EACCES
- **1.5** Create subdirectory
  `…/target-repo/newdir/` → EACCES
- **1.6** Write to sibling
  `…/workspace/other-project/file.txt` → ok
  *Sibling inherits /sandbox read\_write*
- **1.7** Write to parent
  `…/workspace/file.txt` → ok

All `…/` paths are under `/sandbox/workspace/`.

### Category 2 — Read-write (4 tests)

| ID  | Op               | Path             | Exp |
|-----|------------------|------------------|-----|
| 2.1 | Write + readback | /sandbox/test-rw | ok  |
| 2.2 | Write + readback | /tmp/test-rw     | ok  |
| 2.3 | Write            | /dev/null        | ok  |
| 2.4 | Create directory | /sandbox/newdir/ | ok  |

### Category 3 — Read-only (6 tests)

| ID  | Op          | Path               | Exp    |
|-----|-------------|--------------------|--------|
| 3.1 | Read binary | /usr/bin/ls        | ok     |
| 3.2 | Write       | /usr/test-write    | EACCES |
| 3.3 | Read file   | /etc/hostname      | ok     |
| 3.4 | Write       | /etc/test-write    | EACCES |
| 3.5 | Read        | /proc/self/status  | ok     |
| 3.6 | Read 1 byte | /dev/urandom       | ok     |

### Category 4 — Deny / unlisted paths (4 tests)

| ID  | Op    | Path            | Exp    |
|-----|-------|-----------------|--------|
| 4.1 | Read  | /home/          | EACCES |
| 4.2 | Read  | /root/          | EACCES |
| 4.3 | Read  | /opt/           | EACCES |
| 4.4 | Write | /opt/test-write | EACCES |

### Category 5 — Edge cases (3 tests)

- **5.1** Write via symlink
  Create `/tmp/link` → `/etc/passwd`, write through it
  → EACCES
  *Landlock resolves symlink target before policy check*
- **5.2** Write via traversal
  `…/target-repo/../other/file` → ok
  *Resolved path is outside the read\_only subtree*
- **5.3** Delete file
  `…/target-repo/README.md` (unlink) → EACCES
  *Unlink is a write on the parent directory*

## Hypotheses

### Primary

**H0:** Landlock resolves read\_only/read\_write overlap in
favor of the more-specific path.
Confirmed by: tests 1.3, 1.4, 1.5 return EACCES while
1.6, 1.7 succeed.

### Secondary

**H1:** Unlisted paths are completely inaccessible.
Confirmed by: tests 4.1–4.4 return EACCES.

**H2:** Read-only paths permit reads but block writes.
Confirmed by: 3.1, 3.3, 3.5, 3.6 succeed;
3.2, 3.4 return EACCES.

**H3:** Read-write paths permit both operations.
Confirmed by: tests 2.1–2.4 succeed.

**H4:** Landlock resolves symlink targets before checking
policy.
Confirmed by: test 5.1 returns EACCES.

**H5:** Path traversal (`..`) is resolved before policy
check.
Confirmed by: test 5.2 succeeds.

**H6:** `include_workdir: false` prevents implicit
read\_write grants.
Confirmed by: no surprise writable paths beyond those
explicitly listed.

### Environmental

**H7:** OpenShell runs on Fedora 44 (kernel 7.0.10)
despite being outside the support matrix.
Confirmed by: the test completes — sandbox creation,
Landlock enforcement, and SSH all function.

## Success criteria

- All 24 assertions pass
- Every "expect EACCES" test returns errno 13 (EACCES)
  specifically, not errno 2 (ENOENT) — ENOENT means the
  path doesn't exist, indicating a fixture setup problem
- The test runs end-to-end on Fedora without workarounds

## Failure modes

If H0 is refuted (overlap not enforced): significant
finding about Landlock/OpenShell behavior. Investigate
whether it is a Landlock kernel limitation (unlikely —
Landlock is designed for hierarchical path rules) or an
OpenShell policy translation issue (more likely — how
OpenShell maps the YAML to Landlock rulesets).

If H7 is refuted (Fedora doesn't work): document what
fails and fall back to the cloud VM approach from prior
experiments (`experiments/openshell-sandbox-evaluation.md`).

## Prior art

- `experiments/openshell-sandbox-evaluation.md` — first
  OpenShell evaluation, tested network policies and
  container builds. Ran on Ubuntu cloud VM.
- `experiments/openshell-policy-bypass/` — tested
  binary-scoped network policy enforcement and agent
  bypass resistance. Landlock filesystem read-only on
  `/usr` was a supporting enforcement layer there; this
  experiment makes filesystem policy the primary subject.
- `docs/ADRs/0030-openshell-sandbox-interaction-model.md`
  — documents the sandbox interaction model used by
  `fullsend run`, including policy delivery via `--policy`
  flag.
