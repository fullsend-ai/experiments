---
title: "10. Host-side API server for sandboxed agents"
status: Concluded
topics:
  - sandbox
  - tooling
---

# 10. Host-side API server for sandboxed agents

Tracking issue: [fullsend-ai/experiments#25](https://github.com/fullsend-ai/experiments/issues/25)

## What this experiment covers

1. **Basic API server lifecycle** — two API servers started by the
   orchestrator, callable from inside an OpenShell sandbox via the L7 proxy
2. **Credential isolation** — servers hold credentials internally, agents
   never see them
3. **Container build delegation** — Go server builds images via podman
   on the host, working around OpenShell's seccomp restrictions
4. **API discoverability** — three approaches compared: OpenAPI spec,
   tool-use schema, baked-in agent instructions
5. **Per-run auth** — UUID bearer token generated per run
6. **Long-running operations** — container builds that exceed MCP timeout
7. **L7 policy tuning** — most restrictive policy that allows the API

## Architecture

See [design spec](superpowers/2026-05-14-host-side-api-server-design.md).

## Quick start

See [HOW_TO.md](HOW_TO.md).

## Key design decisions

- **Two servers in different languages** (Go + Python) to validate the
  language-agnostic process contract
- **Uniform process contract**: `--port`, `--token`, `/healthz`, SIGTERM
- **Repo provisioner depends on OpenShell#1272**: if content inspection hooks
  ship in OpenShell, the scan-before-copy flow could be handled natively

## Findings

See [results/findings.md](results/findings.md) (populated after running).
