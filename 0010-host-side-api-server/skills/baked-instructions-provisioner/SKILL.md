---
name: baked-instructions-provisioner
description: Hardcoded endpoint documentation for the repo provisioner API.
---

# Repo Provisioner API

Base URL: `$PROVISIONER_URL`

All requests require: `Authorization: Bearer $API_TOKEN`

## POST /repo/provision

Clone a GitHub repository, scan it for security issues, and upload it into the sandbox.

```bash
curl -X POST "$PROVISIONER_URL/repo/provision" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"repo\": \"org/name\",
    \"ref\": \"main\",
    \"dest\": \"/sandbox/repo\",
    \"sandbox\": \"$(hostname | sed 's/^sandbox-//')\"
  }"
```

Request body (JSON):
- `repo` (required): GitHub repository in `org/name` format
- `ref` (optional, default `"main"`): Git ref to check out
- `dest` (optional): Sandbox path to upload the cloned repo to. If omitted, the repo is only scanned but not uploaded.
- `sandbox` (required for upload): Your sandbox name — use `$(hostname | sed 's/^sandbox-//')` to get it.

Response:
```json
{
  "id": "uuid",
  "status": "completed",
  "repo": "org/name",
  "ref": "main",
  "findings": [],
  "dest": "/sandbox/repo"
}
```

Status values: `completed` (clean, uploaded), `rejected` (high-severity findings), `failed` (error).

## GET /repo/status/{id}

Check the status of a provisioning operation by its ID.

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  "$PROVISIONER_URL/repo/status/<operation-id>"
```
