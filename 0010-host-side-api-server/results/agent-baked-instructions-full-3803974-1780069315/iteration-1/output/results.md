# API Server Test Results

**Date:** 2026-05-29

---

## 1. Clone Repository — ✅ SUCCESS

**Endpoint:** `POST $PROVISIONER_URL/repo/provision`

**Request:**
- `repo`: `fullsend-ai/fullsend`
- `ref`: `main`
- `dest`: `/sandbox/fullsend`

**Response:**
- **Status:** `completed`
- **Operation ID:** `452db4f8-8b66-44f2-98d0-fcb2a1fc934b`
- **Findings (4, all medium — not blocking):**
  1. `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` — Prompt injection pattern: `<SYSTEM>` (medium)
  2. `docs/problems/security-threat-model.md` — Prompt injection pattern: `ignore previous instructions` (medium, x2)
  3. `.git/hooks/pre-commit` — Executable git hook (medium)
- **Result:** Repository cloned and uploaded to `/sandbox/fullsend/repo/`

---

## 2. Build Container Image — ✅ SUCCESS

**Endpoint:** `POST $BUILDER_URL/build`

**Request:**
- `tag`: `fullsend-sandbox:test`
- `dockerfile`: `images/sandbox/Containerfile`
- `context_dir`: `/sandbox/fullsend/repo`
- `dest`: `/sandbox/fullsend-sandbox.tar`

**Response:**
- **Status:** `success`
- **Operation ID:** `13705a8c-5f40-490b-9cc4-ed2614fbfd1f`
- **Build:** 36-step Containerfile completed successfully (all layers cached)
- **Final image tag:** `localhost/fullsend-sandbox:test` (`57863a088264`)
- **Image tarball:** `/sandbox/fullsend-sandbox.tar` (4.2 GB)

---

## 3. Endpoints Not Tested (Out of Scope)

| Endpoint | Purpose |
|---|---|
| `GET $PROVISIONER_URL/repo/status/{id}` | Check provisioning status |
| `POST $BUILDER_URL/push` | Push image to registry |
| `GET $BUILDER_URL/images` | List built images |

These were not required by the task. No 403 errors were encountered — all endpoints used responded successfully.

---

## Summary

| Task | Status | Endpoint |
|---|---|---|
| Clone `fullsend-ai/fullsend` (main) → `/sandbox/fullsend` | ✅ Completed | `POST /repo/provision` |
| Build `fullsend-sandbox:test` → `/sandbox/fullsend-sandbox.tar` | ✅ Completed | `POST /build` |
