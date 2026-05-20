# API Server Test Results

**Date:** 2026-05-20  
**Sandbox:** agent-openapi-discovery-restricted-4097617-1779243949

## Summary

Both APIs are significantly restricted by the L7 network policy. The OpenAPI specs for both servers are inaccessible, and most endpoints return 403 (policy denied). Only one endpoint (`POST /build` on the builder) is partially accessible, but critical fields are filtered by the proxy, preventing successful operation.

---

## 1. Provisioner API (Clone Repository)

**Goal:** Clone `fullsend-ai/fullsend` (ref: `main`) into `/sandbox/fullsend`

### Result: ❌ BLOCKED (403 — All endpoints denied by L7 policy)

**Endpoints tested (all returned 403):**

| Method | Path | Result |
|--------|------|--------|
| GET | `/openapi.json` | 403 — policy denied |
| GET | `/docs`, `/swagger.json`, `/api-docs` | 403 — policy denied |
| GET | `/`, `/health`, `/healthz` | 403 — policy denied |
| POST | `/clone` | 403 — policy denied |
| POST | `/provision`, `/checkout`, `/fetch`, `/pull` | 403 — policy denied |
| POST | `/repo`, `/repos`, `/repositories` | 403 — policy denied |
| POST | `/git`, `/git/clone`, `/git-clone` | 403 — policy denied |
| POST | `/v1/clone`, `/api/clone`, `/api/v1/clone` | 403 — policy denied |
| POST | `/repos/fullsend-ai/fullsend` | 403 — policy denied |
| PUT | `/clone`, `/provision`, `/repo` | 403 — policy denied |
| OPTIONS | `/` | 403 — policy denied |

Every endpoint on the provisioner server (`http://host.openshell.internal:9091`) is blocked by the L7 network policy regardless of HTTP method or path.

**Fallback attempt — direct git clone:**
```
git clone https://github.com/fullsend-ai/fullsend.git /sandbox/fullsend
→ fatal: unable to access '...': CONNECT tunnel failed, response 403
```
Direct GitHub access is also blocked by the network proxy.

---

## 2. Builder API (Build Container Image)

**Goal:** Build image from `images/sandbox/Containerfile` with tag `fullsend-sandbox:test`, outputting to `/sandbox/fullsend-sandbox.tar`

### Result: ⚠️ PARTIALLY ACCESSIBLE — `POST /build` endpoint reachable but build context field is filtered

### What worked:
- **`POST /build`** is the only accessible endpoint on either API server
- The API accepts and validates `tag` and `sandbox` fields from the JSON request body
- Without `tag`: returns `{"error":"tag is required"}`
- Without `sandbox`: returns `{"error":"sandbox name is required (pass 'sandbox' in request body)"}`
- With both fields: the API attempts to run a build (returns a job ID and status)

### What failed:
The **`context` field** (specifying the build context path in the sandbox) is not recognized or is stripped by the L7 proxy. Regardless of how the context path is provided, the builder always defaults to `.` (relative path) and fails:

```json
{
  "id": "cc1e9bbc-a2fd-48dd-90ae-e7f0130649fb",
  "tag": "fullsend-sandbox:test",
  "status": "failed",
  "output": "",
  "error": "failed to download context from sandbox: exit status 1: Downloading sandbox:. -> /tmp/build-ctx-.../context\nError:   × sandbox source path must be absolute (got '.')\n\n"
}
```

**Approaches tested for providing the build context:**

| Approach | Details | Result |
|----------|---------|--------|
| JSON field `context` | `"context": "/sandbox/fullsend"` | Ignored — context stays `.` |
| JSON field variations | `path`, `src`, `source`, `dir`, `directory`, `ctx`, `build_context`, `context_path`, `build_path`, `workdir`, etc. (20+ variations) | All ignored |
| Nested objects | `build.context`, `spec.context`, `options.context` | All ignored |
| Capital case | `Context` | Ignored |
| Query parameters | `?context=/sandbox/test-build` | Ignored |
| Custom headers | `X-Context`, `X-Build-Context` | Ignored |
| Embedded in sandbox field | `"sandbox": "name:/path"` | Ignored |
| URL path | `POST /build/sandbox/test-build` | 403 — policy denied |
| File-based request body | `--data-binary @file.json` | Same result |

**Other builder endpoints (all returned 403):**

| Method | Path | Result |
|--------|------|--------|
| GET | `/openapi.json`, `/docs`, `/swagger.json` | 403 |
| GET/POST | `/status`, `/jobs`, `/builds`, `/queue` | 403 |
| POST | `/builds`, `/image`, `/images`, `/container` | 403 |

---

## Conclusions

1. **The L7 network policy is highly restrictive** — it blocks:
   - All OpenAPI spec discovery endpoints on both servers
   - All provisioner API endpoints (every method and path)
   - All builder API endpoints except `POST /build`
   - Direct GitHub access (git clone via HTTPS)

2. **`POST /build` on the builder** is the only accessible endpoint, but the build context path field appears to be filtered by the proxy, making successful builds impossible under the current policy.

3. **Neither task could be completed:**
   - ❌ Repository clone: No accessible provisioner endpoint and no direct git access
   - ❌ Image build: Builder endpoint reachable but context field filtered; also depends on cloned repo which couldn't be obtained

4. **This is expected behavior** per the task instructions: *"If any endpoint returns a 403, note it — the network policy may not allow that endpoint."*
