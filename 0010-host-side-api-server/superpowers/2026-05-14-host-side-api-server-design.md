# Host-Side API Server Experiment Design

Tracking issue: [fullsend-ai/experiments#25](https://github.com/fullsend-ai/experiments/issues/25)

## Goal

Build a working proof-of-concept of host-side API servers that run outside an
OpenShell sandbox and are callable by the agent inside. Validate assumptions
about credential isolation, server lifecycle management, API discoverability,
per-run authentication, long-running operations, and L7 policy tuning. Findings
inform the ADR design (fullsend-ai/fullsend#880).

## Architecture

Four components:

```
┌─────────────────────────────────────────────────────────────┐
│  HOST (CI runner / local machine)                           │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Go Orchestrator                                      │  │
│  │  - Generates per-run UUID bearer token                │  │
│  │  - Starts API servers via uniform process contract    │  │
│  │  - Provisions OpenShell sandbox with L7 policy        │  │
│  │  - Passes endpoint info + token into sandbox          │  │
│  │  - Shuts down servers + sandbox on exit               │  │
│  └───────┬──────────────────────┬────────────────────────┘  │
│          │                      │                           │
│  ┌───────▼──────────┐  ┌───────▼──────────────────────┐    │
│  │  Go API Server   │  │  Python API Server            │    │
│  │  :9090            │  │  :9091                        │    │
│  │                   │  │                               │    │
│  │  Container builds │  │  Secure repo provisioning     │    │
│  │  via podman/docker│  │  clone → scan → copy into     │    │
│  │  on host          │  │  sandbox                      │    │
│  │                   │  │                               │    │
│  │  Holds: registry  │  │  Optionally holds: GitHub     │    │
│  │  credentials      │  │  token (for private repos)    │    │
│  └──────────▲────────┘  └──────────▲──────────────────┘    │
│             │                      │                        │
│  ───────────┼──────────────────────┼────── L7 proxy ──────  │
│             │   10.200.0.1:3128    │                        │
│  ┌──────────┼──────────────────────┼──────────────────────┐ │
│  │  OpenShell Sandbox                                     │ │
│  │                                                        │ │
│  │  Agent (uid 1000, no credentials)                      │ │
│  │  curl → proxy → host API servers                       │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Network path

The agent inside the sandbox reaches host-side servers through the OpenShell
L7 proxy at `10.200.0.1:3128`. The proxy enforces method+path restrictions
per the sandbox's network policy. The host IP is resolved from
`host.openshell.internal` at runtime and added to the policy via `allowed_ips`
to bypass OpenShell's default RFC 1918 SSRF protection (pattern established
in the `agent-scoped-tools-triage` experiment).

## Uniform Process Contract

The orchestrator manages all API servers through the same language-agnostic
interface. Adding a new server in any language requires no changes to the
orchestrator.

**Server requirements:**

- Accept `--port`, `--token`, and optionally `--config` CLI arguments
- Listen on the assigned port
- Respond to `GET /healthz` with 200 when ready
- Shut down cleanly on SIGTERM

**Orchestrator lifecycle per server:**

1. Start process with args
2. Poll `GET /healthz` until 200 (with timeout)
3. Record endpoint for sandbox provisioning
4. On shutdown: send SIGTERM, wait grace period, SIGKILL if needed

## Go API Server: Container Builder

Port: 9090

Holds registry credentials internally. Exposes endpoints for building and
pushing container images using podman or docker on the host. This addresses a
confirmed sandbox limitation: OpenShell's seccomp blocks `CLONE_NEWUSER`,
`AF_NETLINK`, and `setns`, and the agent has zero Linux capabilities, so
neither Docker nor rootless podman/buildah can run inside the sandbox
([NVIDIA/OpenShell#113](https://github.com/NVIDIA/OpenShell/issues/113)).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health check |
| POST | `/build` | Build a container image from a Dockerfile and context |
| POST | `/push` | Push a built image to a registry |
| GET | `/images` | List locally built images |

### Prior art: in-sandbox builds don't work

[fullsend-ai/fullsend#109](https://github.com/fullsend-ai/fullsend/pull/109)
already proved that `podman build` inside an OpenShell sandbox fails due to
seccomp restrictions. This experiment does not re-test that — it focuses on
validating the host-side delegation approach.

### Long-running operation test

Container builds naturally exercise the long-running operation concern. A
build that takes longer than ~60s confirms that the REST API approach handles
operations where MCP's client timeout would fail. The experiment includes a
deliberately slow build (e.g., large base image pull or multi-stage build) to
validate this.

## Python API Server: Secure Repo Provisioner

Port: 9091

Exposes an endpoint that clones a repository, scans it for prompt injection
and malicious content, and copies the clean repo into the sandbox only if
scans pass. Optionally holds a GitHub token for cloning private repos, but the
core value is the scan-before-copy guarantee — the agent cannot bypass the
security scan, even for public repos where no token is needed.

### Dependency on OpenShell#1272

This server exists as a workaround. If
[NVIDIA/OpenShell#1272](https://github.com/NVIDIA/OpenShell/issues/1272) (L7
content inspection hooks — scriptable request/response filtering in the
supervisor) ships, the scan-before-copy flow could be handled natively by
OpenShell's proxy layer without a separate host-side API server. The
experiment should document whether the host-side server approach offers
anything beyond what content inspection hooks would provide (e.g., multi-step
operations like clone+scan+copy as an atomic unit, or richer scan logic that
doesn't fit the stdin/stdout script interface).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | Health check |
| POST | `/repo/provision` | Clone, scan, and copy a repo into the sandbox |
| GET | `/repo/status/{id}` | Check status of a provisioning operation |

### Provisioning flow

1. Agent requests: `POST /repo/provision {"repo": "org/name", "ref": "main"}`
2. Server clones the repo (using its GitHub token if configured, or
   unauthenticated for public repos)
3. Server scans the cloned repo for:
   - `.git/hooks/` with executable content (injected hook execution)
   - Symlinks pointing outside the repo (symlink escape)
   - Known prompt injection patterns in markdown/text files
   - Suspicious binary files
4. If scans pass: server copies the clean repo into the sandbox via SCP
5. If scans fail: server returns findings to the agent (and does not copy)

This tests security scanning as an infrastructure guarantee (agent cannot
bypass the scan) and multi-step operations.

## Per-Run Authentication

A UUID bearer token is generated by the orchestrator at the start of each run.
The token is:

- Passed to each API server via the `--token` CLI argument
- Provisioned into the sandbox as an environment variable
- Validated on every request (`Authorization: Bearer <token>`)
- Invalid or missing tokens receive 401

This validates that per-run auth works as a mechanism. Production could
upgrade to short-lived JWTs with claims (run ID, repo, allowed operations)
without changing the flow.

## API Discoverability

The experiment compares three approaches for making the API known to the
agent. In all cases, the full API is exposed — endpoints the agent's L7 policy
doesn't allow result in 403 from the proxy, and the agent learns the boundary
from those responses.

### Approach 1: OpenAPI spec

Each server serves its OpenAPI spec at `GET /openapi.json`. The agent is
instructed to fetch and read the spec to discover available operations.

### Approach 2: Tool-use schema

Each server serves a tool-definition-style schema at `GET /tools.json`,
formatted like tool definitions (name, description, input_schema). The agent
fetches this to discover operations. Invocation remains plain HTTP/curl, not
MCP.

### Approach 3: Baked-in agent instructions

The API documentation is hardcoded in the agent's definition file. No runtime
discovery — the agent knows the API from its system prompt.

### Evaluation criteria

- How reliably does the agent discover and correctly call endpoints?
- How does the agent handle 403s from policy-blocked endpoints?
- Which approach requires the least prompting to get correct behavior?
- Which approach is most maintainable as the API evolves?

### Future direction: policy-driven tool discovery

Ideally, the agent should only learn about endpoints it can actually reach —
the intersection of the server's API and the agent's L7 policy. This could
take the form of a tool-definition file placed in the sandbox on creation and
updated on policy hot-reload, similar to how MCP servers advertise their
tools. Filing an issue in OpenShell to explore this natively is being
considered.

## L7 Policy Tuning

Write the most restrictive L7 network policy that still allows the agent to
use both API servers. Building on patterns from the `agent-scoped-tools-triage`
and `openshell-policy-bypass` experiments:

- Allow only the specific host IP (resolved from `host.openshell.internal`) with
  `allowed_ips: {{HOST_IP}}/32`
- Restrict to the two server ports (9090, 9091)
- Restrict HTTP methods and paths per endpoint
- Scope by binary identity (only `curl` can reach the API servers)
- Document the minimal policy that works

The experiment should also test what happens when policy is more restrictive
than the API (some endpoints blocked) and confirm the agent handles 403s
gracefully.

## Experiment Structure

```
experiments/host-side-api-server/
├── README.md                        # Experiment overview and findings
├── HOW_TO.md                        # Reproduction steps (Purpose, Requirements,
│                                    # Steps, Expected Output)
├── setup.sh                         # Environment and dependency setup
├── run.sh                           # Run the full experiment
├── orchestrator/
│   ├── main.go                      # Go orchestrator
│   ├── go.mod
│   └── go.sum
├── servers/
│   ├── builder/
│   │   ├── main.go                  # Go container build server
│   │   ├── go.mod
│   │   └── go.sum
│   └── repo-provisioner/
│       ├── server.py                # Python secure repo provisioner
│       └── requirements.txt
├── policies/
│   ├── full-access.yaml             # All endpoints allowed (baseline)
│   └── restricted.yaml              # Minimal policy (tuned)
├── agents/
│   ├── openapi-discovery.md         # Agent using OpenAPI approach
│   ├── tooluse-discovery.md         # Agent using tool-use schema approach
│   └── baked-instructions.md        # Agent with hardcoded API docs
└── results/                         # Output from experiment runs
    └── findings.md                  # Experiment results and recommendations
```

## What This Experiment Does NOT Cover

- Integration with `fullsend run` CLI — this is a standalone experiment
- Production-grade error handling or retry logic
- JWT-based authentication (deferred; UUID token validates the flow)
- Policy-driven dynamic tool discovery (see future direction above)
- Multi-agent scenarios (single agent per run)
