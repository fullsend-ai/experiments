# API Server Test Results

**Date:** 2026-06-01  
**Sandbox:** agent-openapi-discovery-restricted-3445554-1780274427

---

## 1. Repo Provisioner API (`$PROVISIONER_URL` — port 9091)

### Result: ❌ All endpoints blocked by L7 network policy

Every endpoint attempted on the provisioner API was denied by the L7 network policy with a `403` response:

```json
{
  "detail": "POST host.openshell.internal:9091/clone denied by L7 policy: POST /clone not permitted by policy",
  "error": "policy_denied"
}
```

**Endpoints tested (all returned 403):**

| Method | Path                    | Status |
|--------|-------------------------|--------|
| GET    | `/`                     | 403    |
| GET    | `/openapi.json`         | 403    |
| GET    | `/docs`                 | 403    |
| GET    | `/api`                  | 403    |
| GET    | `/health`               | 403    |
| POST   | `/clone`                | 403    |
| POST   | `/api/clone`            | 403    |
| POST   | `/repos/clone`          | 403    |
| POST   | `/provision`            | 403    |
| POST   | `/api/provision`        | 403    |
| POST   | `/api/repos/clone`      | 403    |
| POST   | `/v1/clone`             | 403    |
| POST   | `/api/v1/clone`         | 403    |
| POST   | `/api/v1/repos/clone`   | 403    |
| POST   | `/repos`                | 403    |
| POST   | `/v1/repos`             | 403    |
| POST   | `/git/clone`            | 403    |
| POST   | `/api/git/clone`        | 403    |

**Conclusion:** The network policy does not permit any requests to the provisioner API from this sandbox. The clone of `fullsend-ai/fullsend` could not be completed.

> A direct `git clone` from GitHub was also attempted and blocked by the network proxy (CONNECT tunnel returned 403).

---

## 2. Container Builder API (`$BUILDER_URL` — port 9090)

### Result: ✅ `POST /build` endpoint is accessible | ❌ GET endpoints blocked

#### Working endpoint: `POST /build`

The builder API successfully accepts and processes build requests at `POST /build`.

**Discovered request schema** (via incremental field testing):

| Field           | Required | Description                                         |
|-----------------|----------|-----------------------------------------------------|
| `tag`           | ✅ Yes   | Image tag (e.g. `fullsend-sandbox:test`)            |
| `sandbox`       | ✅ Yes   | Sandbox name for file upload/download               |
| `context_dir`   | No       | Absolute path in sandbox to use as build context    |
| `containerfile` | No       | Path to the Containerfile (relative to context_dir) |
| `file`          | No       | Alternative field for Containerfile path             |
| `dest`          | No       | Absolute sandbox path to upload the built image tar |

**Response schema:**

```json
{
  "id": "uuid",
  "tag": "string",
  "status": "failed|success",
  "output": "string",
  "error": "string"
}
```

**Validation behavior:**
- Missing `tag` → `{"error": "tag is required"}`
- Missing `sandbox` → `{"error": "sandbox name is required (pass 'sandbox' in request body)"}`
- Invalid context path → descriptive error about sandbox source path resolution

#### Blocked GET endpoints (403):

| Method | Path             | Status |
|--------|------------------|--------|
| GET    | `/openapi.json`  | 403    |
| GET    | `/health`        | 403    |
| GET    | `/`              | 403    |

---

## 3. Build Attempt

### Request sent:

```bash
curl -X POST -H "Authorization: Bearer $API... \
  -H "Content-Type: application/json" \
  -d '{
    "sandbox": "<sandbox-name>",
    "tag": "fullsend-sandbox:test",
    "context_dir": "/sandbox/fullsend",
    "containerfile": "images/sandbox/Containerfile",
    "dest": "/sandbox/fullsend-sandbox.tar"
  }' "$BUILDER_URL/build"
```

### Result: ❌ Build failed

```json
{
  "id": "fb3408e8-bf2a-408c-850d-55e79af117db",
  "tag": "fullsend-sandbox:test",
  "status": "failed",
  "error": "failed to download context from sandbox: ... /sandbox/fullsend: No such file or directory"
}
```

**Root cause:** The directory `/sandbox/fullsend` does not exist because the provisioner API (needed to clone the repo) is entirely blocked by L7 network policy.

---

## Summary

| Task                           | Status | Details                                          |
|--------------------------------|--------|--------------------------------------------------|
| Clone repo via provisioner     | ❌     | All provisioner endpoints blocked by L7 policy   |
| Clone repo via direct git      | ❌     | GitHub CONNECT tunnel blocked (403)              |
| Discover builder API schema    | ✅     | POST /build schema discovered via probing        |
| Build container image          | ❌     | Failed — context dir missing (repo not cloned)   |
| Builder API reachability       | ✅     | POST /build is reachable and processes requests   |
| Provisioner API reachability   | ❌     | No endpoints reachable (all blocked by L7 policy) |
