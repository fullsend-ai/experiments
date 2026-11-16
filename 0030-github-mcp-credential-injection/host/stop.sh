#!/usr/bin/env bash
set -euo pipefail

podman rm --force fullsend-github-mcp >/dev/null 2>&1 || true
