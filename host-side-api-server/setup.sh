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

# Ensure podman socket is running
PODMAN_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
if [[ ! -S "$PODMAN_SOCKET" ]]; then
    echo "Podman socket not found. Starting it..."
    systemctl --user start podman.socket 2>/dev/null || {
        mkdir -p "$(dirname "$PODMAN_SOCKET")"
        podman system service --time=0 "unix://${PODMAN_SOCKET}" &
    }
    for i in $(seq 1 15); do
        if [[ -S "$PODMAN_SOCKET" ]] && podman info &>/dev/null 2>&1; then
            break
        fi
        if [[ $i -eq 15 ]]; then
            echo "ERROR: Podman socket not ready after 15s"
            exit 1
        fi
        sleep 1
    done
fi

echo "Podman is running."

# Pinned OpenShell version — keep in sync with fullsend action.yml
OPENSHELL_VERSION="0.0.43"
SUPERVISOR_IMAGE="ghcr.io/nvidia/openshell/supervisor:latest"

# Ensure openshell-gateway binary is available
if ! command -v openshell-gateway &>/dev/null; then
    echo "openshell-gateway not found. Downloading v${OPENSHELL_VERSION}..."
    arch="$(uname -m)"
    case "${arch}" in
        x86_64) ;;
        aarch64|arm64) arch=aarch64 ;;
        *) echo "ERROR: Unsupported architecture: ${arch}"; exit 1 ;;
    esac
    GATEWAY_ASSET="openshell-gateway-${arch}-unknown-linux-gnu.tar.gz"
    GATEWAY_URL="https://github.com/NVIDIA/OpenShell/releases/download/v${OPENSHELL_VERSION}/${GATEWAY_ASSET}"
    curl -fsSL "${GATEWAY_URL}" -o "/tmp/${GATEWAY_ASSET}"
    tar xzf "/tmp/${GATEWAY_ASSET}" -C "${HOME}/.local/bin"
    rm -f "/tmp/${GATEWAY_ASSET}"
    echo "Installed openshell-gateway v${OPENSHELL_VERSION} to ~/.local/bin/"
fi

# Pull supervisor image if missing
if ! podman image exists "${SUPERVISOR_IMAGE}" 2>/dev/null; then
    echo "Pulling supervisor image..."
    podman pull "${SUPERVISOR_IMAGE}"
fi

# Start gateway if not running
if ! curl -sf http://127.0.0.1:18081/healthz &>/dev/null; then
    echo "Starting openshell-gateway..."
    OPENSHELL_SSH_HANDSHAKE_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" \
    OPENSHELL_SUPERVISOR_IMAGE="${SUPERVISOR_IMAGE}" \
    openshell-gateway \
      --bind-address 0.0.0.0 \
      --port 18080 \
      --health-port 18081 \
      --drivers podman \
      --disable-tls \
      --db-url "sqlite:/tmp/openshell-gateway.db?mode=rwc" \
      --log-level info >/tmp/openshell-gateway.log 2>&1 &

    # Register gateway with CLI if not already configured
    if ! openshell gateway list 2>/dev/null | grep -q podman-local; then
        openshell gateway add http://127.0.0.1:18080 --local --name podman-local 2>/dev/null || true
        openshell gateway select podman-local 2>/dev/null || true
    fi

    for i in $(seq 1 30); do
        if curl -sf http://127.0.0.1:18081/healthz &>/dev/null; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            echo "ERROR: Gateway failed to start after 15s. Logs:"
            cat /tmp/openshell-gateway.log 2>/dev/null
            exit 1
        fi
        sleep 0.5
    done
fi

echo "OpenShell gateway is healthy."

# Build Go binaries
mkdir -p bin

echo "Building Go builder server..."
(cd servers/builder && go build -o ../../bin/builder-server .)

mkdir -p results
echo ""
echo "Setup complete. Run ./run.sh <harness-name> to start the experiment."
