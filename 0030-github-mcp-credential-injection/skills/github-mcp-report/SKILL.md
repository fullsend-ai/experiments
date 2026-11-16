---
name: github-mcp-report
description: Read the authenticated GitHub user's profile through GitHub MCP and write a report.
---

# GitHub MCP Report

Use only tools from the configured `github` MCP server. Discover the available
tools, then call `get_me` exactly once. Do not use `gh`, `git`, `curl`,
WebFetch, WebSearch, or direct GitHub API requests.

1. Call `get_me` with no parameters.
2. Create `../output/github-mcp-report.md` with this structure:

   ```markdown
   # GitHub MCP authenticated identity result

   - **Tool:** `get_me`
   - **Authentication-required operation:** passed
   - **Login:** <login from the response>
   - **User ID:** <numeric ID from the response>
   - **Profile URL:** <profile URL from the response>
   ```

   Do not include email, token data, authorization headers, unnecessary profile
   fields, or the complete API response.

   The working directory is `/sandbox/workspace/<target>`. Create
   `/sandbox/workspace/output` first. Do not use `$FULLSEND_OUTPUT_DIR` with
   Fullsend 0.54.0 because that version does not extract from its value.
3. Return the same sanitized information and state that the artifact is
   `github-mcp-report.md`.
4. If the MCP request fails, report the exact error and do not create a
   misleading success artifact.
6. Never print credentials, authorization headers, placeholders, or MCP
   configuration.
