# API Server Test Results

**Date:** 2026-06-01

---

## 1. Repository Cloning (Provisioner API)

**Endpoint:** `POST /repo/provision`  
**Status:** ✅ **Success**

| Field | Value |
|-------|-------|
| Repo | `fullsend-ai/fullsend` |
| Ref | `main` |
| Destination | `/sandbox/fullsend` |
| Operation ID | `99b5a6fd-215d-451b-9bb1-d3cefec20b10` |
| Status | `completed` |

### Security Findings (all medium — none blocking)

| File | Issue | Severity |
|------|-------|----------|
| `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` | Prompt injection pattern: `<SYSTEM>` | medium |
| `docs/problems/security-threat-model.md` | Prompt injection pattern: ignore previous instructions | medium |
| `docs/problems/security-threat-model.md` | Prompt injection pattern: ignore previous instructions | medium |
| `.git/hooks/pre-commit` | Executable git hook | medium |

The repo was successfully cloned and uploaded to `/sandbox/fullsend/repo/`.

---

## 2. Container Image Build (Builder API)

**Endpoint:** `POST /build`  
**Status:** ✅ **Success**

| Field | Value |
|-------|-------|
| Tag | `fullsend-sandbox:test` |
| Dockerfile | `images/sandbox/Containerfile` |
| Context Directory | `/sandbox/fullsend/repo` |
| Destination | `/sandbox/fullsend-sandbox.tar` |
| Operation ID | `f7b524ea-1f83-43fd-87f3-fb9471e7b834` |
| Status | `success` |
| Image Size | ~4.2 GB |

The build completed all 36 steps successfully (most from cache). The final image was tagged as `fullsend-sandbox:test` and the tarball was uploaded to `/sandbox/fullsend-sandbox.tar`.

### Build highlights
- Base image: `ghcr.io/nvidia/openshell-community/sandboxes/base`
- Installs: rsync, jq, Claude CLI, ProtectAI DeBERTa-v3 prompt-injection model (ONNX), ONNX Runtime 1.24.1, Gitleaks 8.30.1, pre-commit, gitlint, jsonschema, Tirith, Atlassian CLI
- All cached layers were reused for a fast build

---

## 3. Endpoints Not Tested / 403 Notes

- `POST /push` — Not tested (not required by task; may return 403 per network policy).
- `GET /images` — Not tested (not required by task).
- `GET /repo/status/{id}` — Not tested (provisioning completed synchronously).

No 403 errors were encountered during the tested operations.

---

## Summary

| Task | API | Endpoint | Result |
|------|-----|----------|--------|
| Clone repo | Provisioner | `POST /repo/provision` | ✅ Completed |
| Build image | Builder | `POST /build` | ✅ Success |

Both tasks completed successfully with no errors or 403 responses.
