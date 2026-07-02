# API Task Results

## 1. Repository Clone — ✅ Success

**Endpoint:** `POST $PROVISIONER_URL/repo/provision`

**Request:**
```json
{
  "repo": "fullsend-ai/fullsend",
  "ref": "main",
  "dest": "/sandbox/fullsend",
  "sandbox": "<sandbox-name>"
}
```

**Result:**
- **Status:** `completed`
- **Operation ID:** `27d8cf99-f519-441e-8c1b-3993bca7fe65`
- **Destination:** `/sandbox/fullsend/repo/`
- **Security Findings (all medium, non-blocking):**
  - `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` — Prompt injection pattern: `<SYSTEM>`
  - `docs/problems/security-threat-model.md` — Prompt injection pattern: `ignore previous instructions` (×2)
  - `.git/hooks/pre-commit` — Executable git hook

The repo was cloned, scanned, and uploaded successfully despite the medium-severity findings.

---

## 2. Container Image Build — ✅ Success

**Endpoint:** `POST $BUILDER_URL/build`

**Request:**
```json
{
  "tag": "fullsend-sandbox:test",
  "dockerfile": "images/sandbox/Containerfile",
  "context_dir": "/sandbox/fullsend/repo",
  "dest": "/sandbox/fullsend-sandbox.tar",
  "sandbox": "<sandbox-name>"
}
```

**Result:**
- **Status:** `success`
- **Operation ID:** `d62a038c-acb1-40c3-9def-549a08b88424`
- **Tag:** `fullsend-sandbox:test`
- **Image tarball:** `/sandbox/fullsend-sandbox.tar` (4.2 GB)
- **Build steps:** 36/36 completed (all cached layers)
- The Containerfile installs Claude CLI, ProtectAI DeBERTa-v3 model, ONNX Runtime, Gitleaks, pre-commit, Tirith, and ACLI on top of the OpenShell base sandbox image.

---

## 3. Access Control / 403 Status

No 403 errors were encountered. All endpoints used (`/repo/provision`, `/build`) responded successfully.

### Endpoints Tested

| Server       | Endpoint            | Method | Status |
|-------------|---------------------|--------|--------|
| Provisioner | `/openapi.json`     | GET    | ✅ 200  |
| Provisioner | `/repo/provision`   | POST   | ✅ 200  |
| Builder     | `/openapi.json`     | GET    | ✅ 200  |
| Builder     | `/build`            | POST   | ✅ 200  |

### Endpoints Not Tested (available per OpenAPI spec)

| Server      | Endpoint            | Method | Notes                              |
|------------|---------------------|--------|------------------------------------|
| Provisioner | `/repo/status/{id}` | GET    | Status polling (not needed; provision returned synchronously) |
| Builder     | `/healthz`          | GET    | Health check                       |
| Builder     | `/images`           | GET    | List images                        |
| Builder     | `/push`             | POST   | Push image to registry             |
