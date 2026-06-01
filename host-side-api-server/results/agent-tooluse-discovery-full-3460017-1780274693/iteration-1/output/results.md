# API Test Results

## 1. Repository Cloning — ✅ SUCCESS

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

**Result:** Completed successfully. The repository was cloned to `/sandbox/fullsend/repo/`.

**Security scan findings (all medium severity, non-blocking):**
| File | Issue |
|------|-------|
| `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` | Prompt injection pattern: `<SYSTEM>` |
| `docs/problems/security-threat-model.md` | Prompt injection pattern: `ignore previous instructions` (×2) |
| `.git/hooks/pre-commit` | Executable git hook |

**Provisioning ID:** `a3801035-5e39-41da-b46e-8f398630337a`

---

## 2. Container Image Build — ✅ SUCCESS

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

**Result:** Image built successfully and uploaded to `/sandbox/fullsend-sandbox.tar` (4.2 GB).

- All 36 build steps completed (all cache hits)
- Final image tag: `localhost/fullsend-sandbox:test`
- Image SHA: `57863a0882647701b0de069228dc2b3a54266a982c9eeca3671cc10d9af0ae10`

**Build ID:** `eee9c677-822f-4b24-8a9c-32993a34e7fa`

---

## 3. Additional API Endpoints Discovered

### Provisioner API
| Endpoint | Method | Status |
|----------|--------|--------|
| `/tools.json` | GET | ✅ Accessible |
| `/repo/provision` | POST | ✅ Accessible |
| `/repo/status/{id}` | GET | Available (not tested — provision returned synchronously) |

### Builder API
| Endpoint | Method | Status |
|----------|--------|--------|
| `/tools.json` | GET | ✅ Accessible |
| `/build` | POST | ✅ Accessible |
| `/push` | POST | Not tested |
| `/images` | GET | Not tested |

---

## Summary

Both core operations completed successfully with no 403 errors encountered. The provisioner cloned the repo, ran a security scan (4 medium-severity findings, none blocking), and uploaded it to the sandbox. The builder built the container image from the Containerfile (36 steps, fully cached) and uploaded the 4.2 GB tarball back to the sandbox.
