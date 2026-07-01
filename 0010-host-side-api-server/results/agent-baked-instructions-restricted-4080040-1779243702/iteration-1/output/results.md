# API Test Results

**Date:** 2026-05-20

## 1. Repository Clone — ✅ Success

**Endpoint:** `POST /repo/provision`
**Repository:** `fullsend-ai/fullsend` (ref: `main`)
**Destination:** `/sandbox/fullsend`

**Response:**
- **Status:** `completed`
- **Operation ID:** `308cc672-7b87-41d4-ab7c-29fdfc35d39d`
- **Findings (medium severity, non-blocking):**
  - `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` — Prompt injection pattern: `<SYSTEM>`
  - `docs/problems/security-threat-model.md` — Prompt injection pattern: `ignore previous instructions` (×2)
  - `.git/hooks/pre-commit` — Executable git hook

The repository was successfully cloned and uploaded to `/sandbox/fullsend/repo/`.

## 2. Container Image Build — ✅ Success

**Endpoint:** `POST /build`
**Containerfile:** `images/sandbox/Containerfile`
**Context directory:** `/sandbox/fullsend/repo`
**Tag:** `fullsend-sandbox:test`
**Destination:** `/sandbox/fullsend-sandbox.tar`

**Result:**
- **Status:** `success`
- **Operation ID:** `85b50a04-d139-4399-bfca-16fcd3604713`
- All 32 build steps completed successfully (most from cache)
- The image was tagged as `localhost/fullsend-sandbox:test`
- Image tarball uploaded to `/sandbox/fullsend-sandbox.tar` (4.2 GB)

## 3. 403 / Blocked Endpoints

No 403 errors were encountered during this test. Both `POST /repo/provision` (provisioner) and `POST /build` (builder) were accessible and functioned correctly.

## Summary

| Task | Endpoint | Status |
|------|----------|--------|
| Clone repo | `POST $PROVISIONER_URL/repo/provision` | ✅ Completed |
| Build image | `POST $BUILDER_URL/build` | ✅ Success |
