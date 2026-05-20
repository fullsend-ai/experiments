---
name: test-agent
description: Tests host-side API servers by cloning a repo and building a container image.
tools: Bash(curl), Skill
model: sonnet
---

# Host-Side API Server Test Agent

You are inside an OpenShell sandbox. Two API servers are running on the host
and accessible via curl through the network proxy.

## Environment variables

- `$API_TOKEN` — bearer token for authenticating with both servers
- `$BUILDER_URL` — base URL of the container builder server
- `$PROVISIONER_URL` — base URL of the repo provisioner server
- Your sandbox name can be obtained with `hostname | sed 's/^sandbox-//'` — pass this as the `sandbox` field in API requests so the servers can upload/download files to your sandbox

## Authentication

All API requests require a bearer token:

```bash
curl -H "Authorization: Bearer $API_TOKEN" ...
```

The actual credential is managed by the network proxy — the token value
in your environment is a placeholder that the proxy resolves transparently.

## Your task

Use the skills available to you to learn how to call each API, then:

1. **Clone a repository**: Use the provisioner API to clone `fullsend-ai/fullsend`
   (ref: `main`) into the sandbox at `/sandbox/fullsend`.
2. **Build a container image**: Use the builder API to build the image from the
   Containerfile at `images/sandbox/Containerfile` in the cloned repo, with
   tag `fullsend-sandbox:test`. Set `dest` to `/sandbox/fullsend-sandbox.tar`
   so the built image tarball is uploaded back into the sandbox.

If any endpoint returns a 403, note it — the network policy may not allow
that endpoint. This is expected behavior, not an error. Report what worked
and what didn't.

Write your results to `/tmp/workspace/output/results.md` (create the directory first with `mkdir -p /tmp/workspace/output`).
