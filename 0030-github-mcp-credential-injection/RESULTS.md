# Results: GitHub MCP credential injection

## Identity-check run

The revised identity-check run succeeded on 2026-11-16.

| Field | Result |
|---|---|
| Run ID | `fs-git-740348a6726d` |
| Fullsend | `0.54.0` |
| OpenShell | `0.1.4` |
| Runtime | Claude Code `2.1.306` |
| Requested model | Fullsend `sonnet` alias |
| Served model | `claude-sonnet-4-6` |
| MCP tool | `get_me` |
| Authentication-required operation | Passed |

Vertex AI did not serve the then-default `claude-sonnet-5-5`, so Fullsend used
its built-in `claude-sonnet-4-6` fallback.

The agent discovered the configured GitHub MCP server and its available tool at
runtime, then called `get_me` and wrote the sanitized artifact in
[`results/github-mcp-report.md`](results/github-mcp-report.md):

```markdown
# GitHub MCP authenticated identity result

- **Tool:** `get_me`
- **Authentication-required operation:** passed
- **Login:** maruiz93
- **User ID:** 15313663
- **Profile URL:** https://github.com/maruiz93
```

The relevant control flow is preserved in the [sanitized transcript](results/transcript.md).
The raw JSONL transcript was intentionally not committed because it contains the
complete profile response and internal runtime metadata.

## Observations

- An unauthenticated request to the local MCP endpoint returned HTTP `401`.
- The MCP server ran with `readOnly=true` and exposed only `get_me`.
- OpenShell permitted MCP initialization, tool discovery, and the `get_me` call.
- The sandbox did not receive `GH_TOKEN` or a GitHub provider.
- The sandbox was deleted after the successful run.
- The local MCP server was stopped after the run.
- The agent transcript shows exactly one `get_me` call and no permission
  denials or subagents.
- Targeted pre-commit checks passed, including experiment numbering,
  frontmatter, and index validation.

## Conclusion

The run supports the hypothesis for the tested Claude, Fullsend, OpenShell,
and pinned GitHub MCP versions. OpenShell injected the GitHub credential at the
gateway, allowing the sandboxed agent to authorize GitHub's authentication-
required `GET /user` operation without exposing the PAT to the sandbox.

This result demonstrates the authenticated MCP path, not general GitHub access.
The server and OpenShell policy were intentionally restricted to one
read-only tool, and the PAT remains sensitive and must be revoked after use.

The original public-file run (`fs-git-cd02ea8590f6`) established MCP
connectivity and the credential boundary but was insufficient evidence of
authenticated GitHub authorization. The `get_me` run is the decisive follow-up.
