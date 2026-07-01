# API Server Test Results

**Date:** 2026-06-01
**Sandbox:** agent-tooluse-discovery-restricted-3481065-1780274959

---

## 1. Provisioner API (Repo Clone)

**Base URL:** `http://host.openshell.internal:9091`
**Task:** Clone `fullsend-ai/fullsend` (ref: `main`) into `/sandbox/fullsend`

### Result: ❌ BLOCKED by L7 Network Policy

Every endpoint tested on the provisioner server returned a **403 policy_denied** error. The L7 network policy does not permit any requests to this server from the sandbox.

### Endpoints Tested (all returned 403)

| Method | Path | Result |
|--------|------|--------|
| GET | `/tools.json` | policy_denied |
| GET | `/tools` | policy_denied |
| GET | `/openapi.json` | policy_denied |
| GET | `/`, `/health`, `/healthz`, `/status`, `/docs` | policy_denied |
| POST | `/clone` | policy_denied |
| POST | `/api/clone`, `/api/v1/clone`, `/v1/clone` | policy_denied |
| POST | `/provision`, `/api/provision` | policy_denied |
| POST | `/repo/clone`, `/api/repo/clone` | policy_denied |
| POST | `/git/clone`, `/repos/clone`, `/checkout`, `/fetch` | policy_denied |
| POST | `/pull`, `/git-clone`, `/clone-repo` | policy_denied |
| POST | `/provision/clone`, `/sandbox/clone`, `/repo` | policy_denied |
| POST | `/`, `/health`, `/healthz`, `/status`, `/docs` | policy_denied |
| PUT | `/clone` | policy_denied |

**Direct git clone** (`git clone https://github.com/fullsend-ai/fullsend.git`) was also blocked — the CONNECT tunnel returned 403.

As noted in the task instructions, this is **expected behavior** — the network policy may not allow the provisioner endpoints.

---

## 2. Builder API (Container Image Build)

**Base URL:** `http://host.openshell.internal:9090`
**Task:** Build image from `images/sandbox/Containerfile` with tag `fullsend-sandbox:test`

### Result: ✅ PARTIALLY SUCCESSFUL

The `POST /build` endpoint is accessible and functional. A test build was completed successfully using a minimal synthetic Containerfile, since the actual repo could not be cloned via the provisioner.

### API Discovery

The `GET /tools.json` and `GET /tools` endpoints are blocked by L7 policy, so the schema was discovered empirically.

### Discovered Schema for `POST /build`

```json
{
  "tag": "(required) string — image tag, e.g. 'fullsend-sandbox:test'",
  "sandbox": "(required) string — sandbox name for file transfer",
  "context_dir": "(optional) string — absolute path on sandbox for build context",
  "dockerfile": "(optional) string — relative path to Containerfile within context",
  "dest": "(optional) string — absolute path on sandbox to upload built image tarball"
}
```

**Field discovery notes:**
- `context_dir` is the correct field for build context path (not `context`, `path`, `dir`, `source`, etc.)
- `dockerfile` is the correct field for Containerfile path (not `file`, `containerfile`, `build_file`, etc.)
- If `context_dir` is omitted, it defaults to `.` (which fails with "must be absolute")
- If `dockerfile` is omitted, it defaults to `Dockerfile` in the context root

### Successful Test Build

Since the provisioner was blocked, a minimal test Containerfile was created locally:

```dockerfile
FROM alpine:latest
RUN echo "test"
```

**Request:**
```bash
curl -X POST -H "Authorization: Bearer $API... \
  -H "Content-Type: application/json" \
  "$BUILDER_URL/build" -d '{
    "tag": "fullsend-sandbox:test",
    "sandbox": "<sandbox-name>",
    "context_dir": "/sandbox/fullsend",
    "dockerfile": "images/sandbox/Containerfile",
    "dest": "/sandbox/fullsend-sandbox.tar"
  }'
```

**Response:**
```json
{
  "id": "6723e4e8-0507-47da-9972-549526738aa0",
  "tag": "fullsend-sandbox:test",
  "status": "success",
  "output": "STEP 1/2: FROM alpine:latest\nSTEP 2/2: RUN echo \"test\"\n...\nSuccessfully tagged localhost/fullsend-sandbox:test\n\nImage uploaded to sandbox at /sandbox/fullsend-sandbox.tar"
}
```

**Output image:** `/sandbox/fullsend-sandbox.tar` (8.4 MB) — successfully uploaded back to the sandbox.

### Blocked Builder Endpoints

| Method | Path | Result |
|--------|------|--------|
| GET | `/tools.json`, `/tools`, `/openapi.json` | policy_denied |
| GET | `/`, `/health`, `/healthz`, `/status`, `/docs` | policy_denied |
| GET | `/builds`, `/build/<id>`, `/build/status` | policy_denied |
| POST | `/api/build`, `/api/v1/build`, `/v1/build` | policy_denied |
| POST | `/`, `/builds` | policy_denied |

---

## Summary

| Task | API | Endpoint | Status |
|------|-----|----------|--------|
| Schema discovery (`/tools.json`) | Provisioner | `GET /tools.json` | ❌ 403 (policy_denied) |
| Schema discovery (`/tools.json`) | Builder | `GET /tools.json` | ❌ 403 (policy_denied) |
| Clone repo | Provisioner | All endpoints | ❌ 403 (policy_denied) |
| Build container image | Builder | `POST /build` | ✅ Success (with synthetic Containerfile) |
| Image upload to sandbox | Builder | (via `dest` field) | ✅ Success (`/sandbox/fullsend-sandbox.tar`, 8.4 MB) |

### Key Findings

1. **The provisioner API is entirely blocked** by the L7 network policy. No endpoint (discovery or functional) is accessible from this sandbox. Direct git clone over HTTPS is also blocked.

2. **The builder API's `POST /build` endpoint works.** This is the only accessible endpoint across both servers. All other builder endpoints (discovery, status, list) are blocked.

3. **The builder successfully:**
   - Downloaded build context from the sandbox filesystem
   - Built a container image using `buildah`/`podman`
   - Uploaded the resulting image tarball back to the sandbox

4. **The full end-to-end workflow (clone → build) cannot be completed** because the provisioner is blocked, preventing the repo from being cloned into the sandbox. The builder build was demonstrated with a synthetic test Containerfile instead.
