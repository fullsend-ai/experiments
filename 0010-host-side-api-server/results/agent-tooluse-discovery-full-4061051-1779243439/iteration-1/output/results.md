# API Test Results

**Date:** 2026-05-20

## 1. Repository Cloning (Provisioner API)

**Endpoint:** `POST /repo/provision`
**Status:** ✅ Success

Cloned `fullsend-ai/fullsend` (ref: `main`) into `/sandbox/fullsend`.

**Request:**
```json
{
  "repo": "fullsend-ai/fullsend",
  "ref": "main",
  "dest": "/sandbox/fullsend",
  "sandbox": "agent-tooluse-discovery-full-4061051-1779243439"
}
```

**Response:** Completed with operation ID `43d8fd0c-f5ed-43e0-8d59-3332352cb5cb`.

**Security scan findings (informational):**
| File | Issue | Severity |
|------|-------|----------|
| `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` | Prompt injection pattern: `<SYSTEM>` | medium |
| `docs/problems/security-threat-model.md` | Prompt injection pattern: ignore previous instructions (×2) | medium |
| `.git/hooks/pre-commit` | Executable git hook | medium |

These are informational findings from the automated security scan; the clone proceeded successfully.

## 2. Container Image Build (Builder API)

**Endpoint:** `POST /build`
**Status:** ✅ Success

Built image `fullsend-sandbox:test` from `images/sandbox/Containerfile` and uploaded tarball to `/sandbox/fullsend-sandbox.tar` (4.2 GB).

**Request:**
```json
{
  "tag": "fullsend-sandbox:test",
  "dockerfile": "images/sandbox/Containerfile",
  "context_dir": "/sandbox/fullsend/repo",
  "sandbox": "agent-tooluse-discovery-full-4061051-1779243439",
  "dest": "/sandbox/fullsend-sandbox.tar"
}
```

**Response:** Build completed successfully with ID `38ea21df-de0d-4e17-afe9-46c832d0de38`. All 32 build steps completed (most from cache). Image tagged as `localhost/fullsend-sandbox:test`.

## 3. API Endpoint Summary

### Provisioner API (`$PROVISIONER_URL`)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/tools.json` | GET | ✅ Accessible |
| `/repo/provision` | POST | ✅ Accessible |
| `/repo/status/{id}` | GET | Not tested (not needed; provision returned synchronously) |

### Builder API (`$BUILDER_URL`)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/tools.json` | GET | ✅ Accessible |
| `/build` | POST | ✅ Accessible |
| `/push` | POST | Not tested |
| `/images` | GET | Not tested |

**No 403 errors were encountered.** All endpoints used in this workflow were fully accessible.
