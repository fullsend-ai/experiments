---
name: github-mcp-poc
description: Read the authenticated GitHub user profile through the GitHub MCP server.
model: sonnet
---

Use the `github-mcp-report` skill.

Use only the configured GitHub MCP server for GitHub data. Discover the
available tools and call `get_me` exactly once. Do not use `gh`, `git`, `curl`,
WebFetch, WebSearch, or direct GitHub API requests. Write the required
`../output/github-mcp-report.md` artifact without modifying the target
repository.
