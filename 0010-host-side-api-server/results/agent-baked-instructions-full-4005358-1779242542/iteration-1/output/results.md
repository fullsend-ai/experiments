# API Server Test Results

**Date:** 2026-05-20

## 1. Repository Clone — Provisioner API

**Endpoint:** `POST /repo/provision`
**Status:** ✅ Success (`completed`)

**Request:**
- `repo`: `fullsend-ai/fullsend`
- `ref`: `main`
- `dest`: `/sandbox/fullsend`

**Response:**
- Operation ID: `27dfbad9-2e0b-48da-ac6f-e68c37ed3e3d`
- Status: `completed`
- Findings (all medium severity, none blocking):
  1. `internal/scaffold/fullsend-repo/skills/code-review/SKILL.md` — Prompt injection pattern: `<SYSTEM>`
  2. `docs/problems/security-threat-model.md` — Prompt injection pattern: `ignore previous instructions` (×2)
  3. `.git/hooks/pre-commit` — Executable git hook
- Repo uploaded to `/sandbox/fullsend/repo/`

## 2. Container Image Build — Builder API

**Endpoint:** `POST /build`
**Status:** ✅ Success

**Request:**
- `tag`: `fullsend-sandbox:test`
- `dockerfile`: `images/sandbox/Containerfile`
- `context_dir`: `/sandbox/fullsend/repo`
- `dest`: `/sandbox/fullsend-sandbox.tar`

**Response:**
- Operation ID: `64011cf0-8e84-4d8f-9852-20425921eeca`
- Status: `success`
- Build completed all 32 steps (used build cache extensively)
- Image tarball uploaded to `/sandbox/fullsend-sandbox.tar` (4.2 GB)

## 3. Endpoint Accessibility Summary

| Endpoint | Method | Status |
|---|---|---|
| `/repo/provision` (Provisioner) | POST | ✅ Accessible |
| `/build` (Builder) | POST | ✅ Accessible |
| `/push` (Builder) | POST | Not tested |
| `/images` (Builder) | GET | Not tested |
| `/repo/status/{id}` (Provisioner) | GET | Not tested |

No 403 errors were encountered. All tested endpoints were reachable and functional.
