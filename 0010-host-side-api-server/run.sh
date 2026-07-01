#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    echo "Usage: $0 <harness-name>"
    echo ""
    echo "Starts the host-side API servers, renders policies, and runs"
    echo "fullsend run with the specified harness."
    echo ""
    echo "Available harnesses:"
    for f in harness/*.yaml; do
        echo "  $(basename "$f" .yaml)"
    done
    echo ""
    echo "Example: $0 baked-instructions-full"
}

if [[ $# -lt 1 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    usage
    exit 0
fi

HARNESS_NAME="$1"
HARNESS_FILE="harness/${HARNESS_NAME}.yaml"

if [[ ! -f "$HARNESS_FILE" ]]; then
    echo "ERROR: Harness file not found: $HARNESS_FILE"
    usage
    exit 1
fi

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

if [[ ! -f bin/builder-server ]]; then
    echo "Binaries not found. Running setup..."
    ./setup.sh
fi

if ! command -v fullsend &>/dev/null; then
    echo "ERROR: fullsend not found in PATH"
    exit 1
fi

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

BUILDER_PID=""
PROVISIONER_PID=""
ENV_FILE="/tmp/api-servers-$$.env"

cleanup() {
    echo ""
    echo "=== Cleaning up ==="
    [[ -n "$BUILDER_PID" ]] && kill "$BUILDER_PID" 2>/dev/null && wait "$BUILDER_PID" 2>/dev/null && echo "Stopped builder (pid $BUILDER_PID)"
    [[ -n "$PROVISIONER_PID" ]] && kill "$PROVISIONER_PID" 2>/dev/null && wait "$PROVISIONER_PID" 2>/dev/null && echo "Stopped provisioner (pid $PROVISIONER_PID)"
    openshell provider delete api-server 2>/dev/null && echo "Deleted provider api-server" || true
    rm -f "$ENV_FILE"
    rm -f policies/rendered-full-access.yaml policies/rendered-restricted.yaml
    echo "Cleanup done."
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Clean up stale state from previous runs
# ---------------------------------------------------------------------------

# Delete stale sandboxes that might hold the provider
for sb in $(openshell sandbox list 2>/dev/null | grep "agent-${HARNESS_NAME}" | awk '{print $1}'); do
    openshell sandbox delete "$sb" 2>/dev/null || true
done
sleep 1
openshell provider delete api-server 2>/dev/null || true

# ---------------------------------------------------------------------------
# Generate token and export for provider creation
# ---------------------------------------------------------------------------

export API_TOKEN
API_TOKEN="$(uuidgen)"

echo "=== Host-Side API Server Experiment ==="
echo "Harness: $HARNESS_NAME"

# ---------------------------------------------------------------------------
# Resolve host IP (needed before starting servers for bind address)
# ---------------------------------------------------------------------------

HOST_IP=""
if out=$(getent hosts host.openshell.internal 2>/dev/null); then
    HOST_IP=$(echo "$out" | awk '{print $1}')
    echo "Host IP (via host.openshell.internal): $HOST_IP"
fi

if [[ -z "$HOST_IP" ]]; then
    HOST_IP=$(podman network inspect podman 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['subnets'][0]['gateway'])" 2>/dev/null)
    if [[ -n "$HOST_IP" ]]; then
        echo "Host IP (via podman bridge gateway): $HOST_IP"
    fi
fi

if [[ -z "$HOST_IP" ]]; then
    echo "ERROR: Could not resolve host IP"
    exit 1
fi

# ---------------------------------------------------------------------------
# Start API servers (bound to all interfaces — rootless Podman can't bind to
# the bridge gateway IP since it lives inside the container namespace)
# ---------------------------------------------------------------------------

# Kill any leftover servers on our ports
for port in 9090 9091; do
    if pid=$(lsof -ti ":${port}" 2>/dev/null); then
        echo "Killing leftover process on port $port (pid $pid)..."
        kill $pid 2>/dev/null
        sleep 0.5
    fi
done

echo ""
echo "Starting builder server on port 9090..."
./bin/builder-server --port 9090 --token "$API_TOKEN" --bind-address "0.0.0.0" &
BUILDER_PID=$!

echo "Starting provisioner server on port 9091..."
python3 ./servers/repo-provisioner/server.py --port 9091 --token "$API_TOKEN" --bind-address "0.0.0.0" &
PROVISIONER_PID=$!

# Wait for health checks, verifying our child processes are still alive
echo "Waiting for servers to be ready..."
declare -A PORT_PID=( [9090]=$BUILDER_PID [9091]=$PROVISIONER_PID )
for port in 9090 9091; do
    for i in $(seq 1 30); do
        if ! kill -0 "${PORT_PID[$port]}" 2>/dev/null; then
            echo "ERROR: Server on port $port (pid ${PORT_PID[$port]}) died on startup"
            exit 1
        fi
        if curl -sf "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then
            echo "  Port $port ready"
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "ERROR: Server on port $port not ready after 15s"
            exit 1
        fi
        sleep 0.5
    done
done

# ---------------------------------------------------------------------------
# Render policies
# ---------------------------------------------------------------------------

echo "Rendering policies..."
sed "s/{{HOST_IP}}/$HOST_IP/g" policies/full-access.yaml > policies/rendered-full-access.yaml
sed "s/{{HOST_IP}}/$HOST_IP/g" policies/restricted.yaml > policies/rendered-restricted.yaml
echo "  policies/rendered-full-access.yaml"
echo "  policies/rendered-restricted.yaml"

# ---------------------------------------------------------------------------
# Generate env file (server URLs only — token is handled by provider)
# ---------------------------------------------------------------------------

cat > "$ENV_FILE" <<'ENVEOF'
export BUILDER_URL='http://host.openshell.internal:9090'
export PROVISIONER_URL='http://host.openshell.internal:9091'
ENVEOF

export EXPERIMENT_ENV_FILE="$ENV_FILE"
echo "Env file: $ENV_FILE"

# ---------------------------------------------------------------------------
# Run fullsend
# ---------------------------------------------------------------------------

echo ""
echo "=== Running fullsend: $HARNESS_NAME ==="
echo ""

fullsend run "$HARNESS_NAME" \
    --fullsend-dir . \
    --target-repo target-repo \
    --output-dir results/

echo ""
echo "=== Experiment complete ==="
echo "Results in: results/"
