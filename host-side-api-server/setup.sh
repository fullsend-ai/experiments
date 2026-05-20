#!/usr/bin/env bash
set -euo pipefail

echo "=== Host-Side API Server Experiment Setup ==="

# Check prerequisites
MISSING=""
for cmd in go python3 openshell podman curl git uuidgen; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING="$MISSING $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required tools:$MISSING"
    exit 1
fi

echo "All prerequisites found."

# Check podman socket
if ! podman info &>/dev/null 2>&1; then
    echo "ERROR: Podman is not reachable. Start it with: systemctl --user start podman.socket"
    exit 1
fi

echo "Podman is running."

# Check openshell gateway
if ! curl -sf http://127.0.0.1:18081/healthz &>/dev/null; then
    echo "ERROR: OpenShell gateway not reachable on port 18081. See HOW_TO.md for setup instructions."
    exit 1
fi

echo "OpenShell gateway is healthy."

# Build Go binaries
mkdir -p bin

echo "Building Go builder server..."
(cd servers/builder && go build -o ../../bin/builder-server .)

mkdir -p results
echo ""
echo "Setup complete. Run ./run.sh <harness-name> to start the experiment."
