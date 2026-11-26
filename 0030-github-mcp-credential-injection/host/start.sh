#!/usr/bin/env bash
set -euo pipefail

readonly image="ghcr.io/github/github-mcp-server@sha256:01860258ff7108e354067e48381869059d3eeb0803121efb6f9d5efd2fb95435"
readonly token_file="${GITHUB_MCP_PAT_FILE:-$HOME/.config/openshell/github-mcp-pat}"

if [[ ! -s "$token_file" ]]; then
  echo "Missing GitHub PAT: $token_file" >&2
  echo "Create a fine-grained, read-only token as described in README.md." >&2
  exit 1
fi
if [[ "$(stat -c '%a' "$token_file")" != "600" ]]; then
  echo "Refusing token file without mode 0600: $token_file" >&2
  exit 1
fi

"$(dirname "$0")/stop.sh"
podman pull "$image" >/dev/null
podman run --detach --rm \
  --name fullsend-github-mcp \
  --publish 0.0.0.0:8766:8082 \
  --env GITHUB_READ_ONLY=1 \
  --env GITHUB_TOOLS=get_me \
  "$image" http --listen-host 0.0.0.0 --port 8082 >/dev/null

for _ in {1..30}; do
  if curl --silent --output /dev/null --max-time 1 http://127.0.0.1:8766/mcp; then
    echo "GitHub MCP is available at http://127.0.0.1:8766/mcp."
    exit 0
  fi
  sleep 0.2
done

echo "GitHub MCP did not become ready; inspect: podman logs fullsend-github-mcp" >&2
exit 1
