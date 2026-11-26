---
title: "30. GitHub MCP credential injection"
status: Concluded
topics:
  - mcp
  - security
  - openshell
---

# 30. GitHub MCP credential injection

Date: 2026-11-13

## Hypothesis

OpenShell can give a sandboxed Fullsend agent narrowly scoped access to an
authenticated MCP server without revealing the real credential to the sandbox.
The MCP server and its available tools should be discoverable by the agent at
runtime, without hard-coding the tool implementation into the agent prompt.
For this experiment, the agent runtime is Claude; pi, OpenCode, and Codex are
explicitly out of scope.

An outsider can reproduce the flow with a public MCP implementation, a
read-only GitHub token, and a public repository.

## Approach

Run the official open source
[`github/github-mcp-server`](https://github.com/github/github-mcp-server)
locally in native HTTP mode. OpenShell places an opaque
`openshell:resolve...` value in the sandbox's MCP configuration and substitutes
the GitHub PAT in the outbound `Authorization` header. The server is configured
read-only and exposes only the authentication-required `get_me` tool; OpenShell
independently permits only that MCP tool.

The Claude agent discovers the configured GitHub MCP server and its available
tool, calls the authentication-required `get_me` operation, and writes a
sanitized identity artifact. It is explicitly prohibited from using `gh`,
`git`, `curl`, web search, or a direct GitHub API call.

The sandbox also cannot reach GitHub's API directly. Its OpenShell profile
exposes only the host-side MCP endpoint at `host.openshell.internal:8766/mcp`.
The profile permits MCP `initialize`, `notifications/initialized`, and
`tools/list`, plus exactly one `tools/call` operation: the `get_me` tool. It
does not permit direct HTTP access to GitHub API endpoints or any other MCP
tool. This network and tool policy is enforced independently of the agent's
prompt restrictions.

```text
Claude Code in Fullsend sandbox
  │ MCP request with opaque credential placeholder
  ▼
OpenShell gateway
  │ substitutes Authorization: Bearer <GitHub PAT>
  ▼
Official GitHub MCP Server on host (read-only, one tool)
  │ authenticated GET /user request
  ▼
authenticated GitHub user profile
```

## Tested versions

| Component | Tested version |
|---|---|
| Fullsend | `0.54.0` |
| OpenShell | `0.1.4` |
| GitHub MCP Server | `v2.1.0`, commit `4bcdcdf8d7beee98c9448e73e257308280924cc4`, built `2026-11-03T11:05:01Z` |
| GitHub MCP image (amd64) | `ghcr.io/github/github-mcp-server@sha256:01860258ff7108e354067e48381869059d3eeb0803121efb6f9d5efd2fb95435` |
| Fullsend sandbox image | `ghcr.io/fullsend-ai/fullsend-sandbox@sha256:8e17e6120e17debdcabff5eb331a7cb7757b09ec3d586010c9d7956fd1fc5633` |
| Claude Code in sandbox | `2.1.306` |
| Podman | `5.8.2` |
| MCP protocol | `2025-11-25` |

The successful run requested Fullsend's `sonnet` alias. Vertex AI did not serve
the then-default `claude-sonnet-5-5`, so Fullsend used its built-in fallback
`claude-sonnet-4-6`. The tested Vertex region was `us-east5`; use a region where
your project has access to the configured model.

## Prerequisites

- Linux on `amd64` (the pinned MCP digest is architecture-specific)
- Podman and `curl`
- Fullsend `0.54.0`
- OpenShell `0.1.4`, with its gateway running
- Google Cloud Application Default Credentials and Vertex AI model access
- A GitHub account able to create a [fine-grained personal access
  token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- A disposable local Git repository to use as Fullsend's target

Commands below start in this experiment directory:

```bash
cd 0030-github-mcp-credential-injection
```

See [HOW_TO.md](HOW_TO.md) for the reproducible setup, run, verification, and
teardown procedure.

The completed run is documented in [RESULTS.md](RESULTS.md), including a
sanitized transcript excerpt.

## Results

The original public-file run succeeded on 2026-11-13 with run ID
`fs-git-cd02ea8590f6`, but it did not prove that the GitHub credential enabled
an authenticated GitHub operation. The experiment was therefore revised to use
`get_me`, which calls GitHub's authentication-required `GET /user` endpoint.

The identity-check run succeeded on 2026-11-16 with run ID
`fs-git-740348a6726d`. Fullsend used the requested `sonnet` alias, fell back
from unavailable `claude-sonnet-5-5` to `claude-sonnet-4-6`, and the agent
discovered and invoked `get_me` through the configured GitHub MCP plugin.
See the detailed [results](RESULTS.md); the generated sanitized artifact is
checked in below:

```markdown
# GitHub MCP authenticated identity result

- **Tool:** `get_me`
- **Authentication-required operation:** passed
- **Login:** `maruiz93`
- **User ID:** `15313663`
- **Profile URL:** https://github.com/maruiz93
```

Additional observations:

- An unauthenticated request to the local MCP endpoint returned HTTP `401`.
- Server logs confirmed `readOnly=true`.
- The server is configured to expose only `get_me`.
- The OpenShell policy allows only MCP initialization, tool discovery, and a
  call to `get_me`.
- No sandbox remained after the successful run.

## Security properties and limits

- The PAT is stored outside Git and must have mode `0600`.
- The user creates the disposable PAT and supplies it explicitly through the
  `GITHUB_MCP_PAT_FILE` path; the experiment does not rely on a pre-existing
  token in a fixed home-directory location.
- The plugin contains `${GITHUB_MCP_PAT}`, not the secret. OpenShell resolves
  the credential at the gateway before forwarding the allowed request.
- The sandbox receives neither `GH_TOKEN` nor a GitHub provider, and its agent
  and skill prohibit alternate GitHub access paths.
- The OpenShell profile exposes only `host.openshell.internal:8766/mcp` and
  allows no direct GitHub API endpoint. Its MCP rules allow only initialization,
  discovery, and a `tools/call` for `get_me`.
- The MCP server and OpenShell both apply restrictions. The server is
  read-only and exposes one tool; OpenShell allows only that same tool.
- Binding to `0.0.0.0:8766` is needed for the sandbox-to-host route. The MCP
  endpoint still requires a valid GitHub bearer token. Use this only on a
  trusted local machine and stop it after the run.
- A PAT remains sensitive even when narrowly scoped. Revoke it when finished.

## Conclusion

The initial run supported the credential-boundary and MCP-connectivity portions
of the hypothesis, but its public-file operation was insufficient evidence of
authenticated GitHub authorization. The revised `get_me` run succeeded:
OpenShell-injected credentials authorized GitHub's `GET /user` operation while
the PAT remained outside the sandbox. The hypothesis is supported for the
tested Claude, Fullsend, OpenShell, and pinned GitHub MCP versions.
