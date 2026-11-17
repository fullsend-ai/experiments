# How to run the GitHub MCP credential injection experiment

## Purpose

Run the Claude Fullsend agent against the official GitHub MCP server through
OpenShell. Verify that Claude discovers and uses the authentication-required
`get_me` tool while the GitHub PAT remains outside the sandbox.

## Requirements

| Requirement | Version / notes |
|---|---|
| Linux | `amd64` for the pinned MCP image |
| Podman and curl | Installed and available on `PATH` |
| Fullsend | `0.54.0` |
| OpenShell | `0.1.4`, with its gateway running |
| Claude runtime | The harness uses `runtime: claude`; pi, OpenCode, and Codex are not tested |
| Google Cloud ADC | Vertex AI access for the configured model |
| GitHub token | Disposable fine-grained PAT with no write permissions |

## Steps

1. Change to this experiment directory:

   ```bash
   cd 0030-github-mcp-credential-injection
   ```

2. Create a disposable, fine-grained, read-only GitHub PAT using GitHub's
   [fine-grained personal access token instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token),
   then store it in a temporary file outside the checkout. Do not grant any
   repository access or write permissions; this experiment only needs the
   authenticated user profile. The experiment does not assume that a token
   already exists on the machine. Keep the generated token available for the
   next step; do not paste it into Git or a tracked file.

3. Store the PAT in a temporary file. Run the commands below in the same shell
   where you will run the rest of the experiment. They work in both Bash and
   Zsh:

   ```bash
   token_file="$(mktemp /tmp/github-mcp-pat.XXXXXX)"
   chmod 600 "$token_file"
   trap 'rm -f "$token_file"' EXIT

   printf 'GitHub fine-grained PAT: '
   stty -echo
   read token
   stty echo
   printf '\n'
   test -n "$token"
   printf '%s' "$token" > "$token_file"
   unset token
   export GITHUB_MCP_PAT_FILE="$token_file"
   test -s "$GITHUB_MCP_PAT_FILE"
   test "$(stat -c '%a' "$GITHUB_MCP_PAT_FILE")" = 600
   ```

   Keep this shell open for the rest of the experiment. The `EXIT` trap removes
   the temporary token file when the shell exits.

   When prompted, paste the PAT you just created and press Enter. Nothing will
   be echoed while you type or paste it. If the prompt or `stty` command is
   interrupted, run `stty echo` before continuing.

4. Start and authenticate-check the MCP server:

   ```bash
   ./host/start.sh
   curl --silent --output /dev/null --write-out '%{http_code}\n' \
     http://127.0.0.1:8766/mcp
   ```

   The unauthenticated check should return `401`.

5. Configure Vertex AI and create a disposable target repository:

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
   export ANTHROPIC_VERTEX_PROJECT_ID="your-gcp-project-id"
   export CLOUD_ML_REGION="a-region-serving-your-model"
   mkdir -p /tmp/github-mcp-target
   git -C /tmp/github-mcp-target init
   ```

6. Validate and run the Claude harness:

   ```bash
   fullsend lint github-mcp-poc --fullsend-dir . --strict
   openshell profile lint --file profiles/github-mcp.yaml
   GITHUB_MCP_PAT="$(<"$GITHUB_MCP_PAT_FILE")" \
   fullsend run github-mcp-poc \
     --fullsend-dir . \
     --target-repo /tmp/github-mcp-target \
     --output-dir /tmp/github-mcp-run \
     --no-post-script
   ```

7. Locate the artifact and compare it with the checked-in result:

   ```bash
   find /tmp/github-mcp-run -path '*/iteration-1/output/github-mcp-report.md' -print
   diff -u results/github-mcp-report.md \
     "$(find /tmp/github-mcp-run -path '*/iteration-1/output/github-mcp-report.md' -print -quit)"
   ```

   The report should show `get_me`, a login, numeric user ID, and profile URL.
   The agent should have discovered the `github` MCP server and available tool
   from the configured plugin. Do not include the token, email, or full profile
    response in the artifact.

## Expected Output

The unauthenticated check in Step 4 should print HTTP `401`. A successful run
should produce `results/github-mcp-report.md` containing the `get_me` tool name,
the authenticated user's login, numeric user ID, and profile URL. The artifact
must not contain the token, email, authorization headers, or full profile
response.

## Repeat runs and troubleshooting

| Symptom | Resolution |
|---|---|
| Missing GitHub PAT | Create a disposable PAT and set `GITHUB_MCP_PAT_FILE` to a file with mode `600`. |
| Port `8766` is occupied | Stop the conflicting service, then rerun `./host/start.sh`. |
| MCP returns `401` during the run | Confirm the token is valid, `GITHUB_MCP_PAT_FILE` points to the intended 0600 file, and `GITHUB_MCP_PAT` was supplied. |
| Vertex model is unavailable | Select a region/project with access and record the change. |
| Existing OpenShell resources | Delete only this experiment's sandbox, provider, and profile before retrying. |

Inspect logs without printing request headers:

```bash
podman logs fullsend-github-mcp
```

## Teardown

```bash
./host/stop.sh
openshell provider delete github-mcp || true
openshell profile delete github-mcp-poc || true
rm -rf /tmp/github-mcp-target /tmp/github-mcp-run
```

The shell `EXIT` trap removes the temporary PAT file. Revoke the fine-grained
PAT in GitHub after the experiment.
