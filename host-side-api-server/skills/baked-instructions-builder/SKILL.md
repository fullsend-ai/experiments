---
name: baked-instructions-builder
description: Hardcoded endpoint documentation for the container builder API.
---

# Container Builder API

Base URL: `$BUILDER_URL`

All requests require: `Authorization: Bearer $API_TOKEN`

## POST /build

Build a container image from a Dockerfile.

```bash
curl -X POST "$BUILDER_URL/build" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tag\": \"myimage:latest\",
    \"dockerfile\": \"Dockerfile\",
    \"context_dir\": \"/sandbox/repo\",
    \"sandbox\": \"$(hostname | sed 's/^sandbox-//')\",
    \"dest\": \"/sandbox/image.tar\"
  }"
```

Request body (JSON):
- `tag` (required): Image tag to build
- `dockerfile` (optional, default `"Dockerfile"`): Path to the Dockerfile relative to `context_dir`
- `context_dir` (required): Path to the build context directory **inside the sandbox** — the server downloads this from your sandbox before building
- `sandbox` (required): Your sandbox name — use `$(hostname | sed 's/^sandbox-//')` to get it
- `dest` (optional): Sandbox path to upload the built image tarball to. If omitted, the image stays on the host only.

Response:
```json
{"id": "uuid", "tag": "myimage:latest", "status": "success", "output": "..."}
```

## POST /push

Push a built image to a registry.

```bash
curl -X POST "$BUILDER_URL/push" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tag": "myimage:latest"}'
```

## GET /images

List locally built container images.

```bash
curl -H "Authorization: Bearer $API_TOKEN" "$BUILDER_URL/images"
```
