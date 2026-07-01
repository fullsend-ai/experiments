# API Test Results

**Date:** 2026-05-20
**Sandbox:** `agent-openapi-discovery-full-4038775-1779243123`

---

## 1. API Discovery

### Provisioner API (`$PROVISIONER_URL`)
- **OpenAPI spec:** `GET /openapi.json` — ✅ Success
- **Endpoints discovered:**
  - `POST /repo/provision` — Clone, scan, and upload a repo into a sandbox
  - `GET /repo/status/{id}` — Check provisioning operation status

### Builder API (`$BUILDER_URL`)
- **OpenAPI spec:** `GET /openapi.json` — ✅ Success
- **Endpoints discovered:**
  - `POST /build` — Build a container image
  - `GET /healthz` — Health check
  - `GET /images` — List container images
  - `POST /push` — Push a container image

---

## 2. Clone Repository

- **Endpoint:** `POST $PROVISIONER_URL/repo/provision`
- **Request payload:**
  ```json
  {
    "repo": "fullsend-ai/fullsend",
    "ref": "main",
    "dest": "/sandbox/fullsend",
    "sandbox": "agent-openapi-discovery-full-4038775-1779243123"
  }
  ```
- **Result:** ✅ **Completed**
- **Operation ID:** `7317ac79-8714-4f71-b39a-08ab10d2bc56`
- **Security scan findings (4 medium-severity, non-blocking):**
  | File | Issue | Severity |
  |------|-------|----------|
  | `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` | Prompt injection pattern: `<SYSTEM>` | medium |
  | `docs/problems/security-threat-model.md` | Prompt injection pattern: ignore previous instructions | medium |
  | `docs/problems/security-threat-model.md` | Prompt injection pattern: ignore previous instructions | medium |
  | `.git/hooks/pre-commit` | Executable git hook | medium |
- **Repo uploaded to:** `/sandbox/fullsend/repo/`

---

## 3. Build Container Image

- **Endpoint:** `POST $BUILDER_URL/build`
- **Request payload:**
  ```json
  {
    "tag": "fullsend-sandbox:test",
    "dockerfile": "images/sandbox/Containerfile",
    "context_dir": "/sandbox/fullsend/repo",
    "dest": "/sandbox/fullsend-sandbox.tar",
    "sandbox": "agent-openapi-discovery-full-4038775-1779243123"
  }
  ```
- **Result:** ✅ **Success**
- **Operation ID:** `cdba87e9-9184-40cb-a44f-2a7ea86d1db4`
- **Image tag:** `fullsend-sandbox:test`
- **Build steps:** 32/32 completed (all cached)
- **Image tarball:** `/sandbox/fullsend-sandbox.tar` (4.2 GB)

---

## 4. 403 / Access Issues

No 403 errors were encountered. All endpoints used in this test responded successfully.

---

## Summary

| Task | Endpoint | Status |
|------|----------|--------|
| Fetch provisioner OpenAPI spec | `GET /openapi.json` | ✅ Success |
| Fetch builder OpenAPI spec | `GET /openapi.json` | ✅ Success |
| Clone `fullsend-ai/fullsend` (ref: `main`) | `POST /repo/provision` | ✅ Completed |
| Build `fullsend-sandbox:test` image | `POST /build` | ✅ Success |
