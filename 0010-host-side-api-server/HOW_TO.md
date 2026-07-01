## Purpose

Run the host-side API server experiment to validate that agents inside an
OpenShell sandbox can call API servers running on the host through the L7
proxy.

## Requirements

| Requirement | Link |
|-------------|------|
| Go 1.23+ | https://go.dev/dl/ |
| Python 3.11+ | https://www.python.org/downloads/ |
| OpenShell CLI v0.0.43+ | https://github.com/NVIDIA/OpenShell |
| openshell-gateway v0.0.43+ | https://github.com/NVIDIA/OpenShell/releases |
| Podman (rootless) | https://podman.io/docs/installation |
| curl | (pre-installed on most systems) |
| git | https://git-scm.com/downloads |

### OpenShell setup

This experiment uses the standalone `openshell-gateway` binary with the
Podman driver — not the older K3s-in-Docker approach (`openshell gateway
start`, removed in v0.0.37).

1. Install Podman and start the socket:
   ```bash
   systemctl --user start podman.socket
   ```

2. Download the `openshell-gateway` binary from the
   [OpenShell releases](https://github.com/NVIDIA/OpenShell/releases)
   page and place it in your `$PATH`.

3. Pull the required images:
   ```bash
   podman pull ghcr.io/nvidia/openshell/supervisor:latest
   podman pull ghcr.io/nvidia/openshell-community/sandboxes/base:latest
   ```

4. Start the gateway:
   ```bash
   OPENSHELL_SSH_HANDSHAKE_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" \
   OPENSHELL_SUPERVISOR_IMAGE="ghcr.io/nvidia/openshell/supervisor:latest" \
   OPENSHELL_SANDBOX_IMAGE="ghcr.io/nvidia/openshell-community/sandboxes/base:latest" \
   OPENSHELL_SANDBOX_IMAGE_PULL_POLICY="missing" \
   openshell-gateway \
     --bind-address 0.0.0.0 \
     --port 18080 \
     --health-port 18081 \
     --drivers podman \
     --disable-tls \
     --db-url "sqlite:/tmp/openshell-gateway.db?mode=rwc" \
     --log-level info &
   ```

5. Register the gateway with the CLI:
   ```bash
   CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/openshell"
   mkdir -p "${CONFIG_DIR}/gateways/podman-local"
   cat > "${CONFIG_DIR}/gateways/podman-local/metadata.json" <<'EOF'
   {
     "name": "podman-local",
     "gateway_endpoint": "http://127.0.0.1:18080",
     "is_remote": false,
     "gateway_port": 18080,
     "auth_mode": "plaintext"
   }
   EOF
   printf 'podman-local' > "${CONFIG_DIR}/active_gateway"
   ```

6. Verify the gateway is healthy:
   ```bash
   curl -sf http://127.0.0.1:18081/healthz
   ```

### Environment variables

| Variable | Description |
|----------|-------------|
| `FULLSEND_GCP_PROJECT_ID` | GCP project with Vertex AI API enabled |
| `CLOUD_ML_REGION` | Vertex AI region (default: `global`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a service account key JSON with `roles/aiplatform.user` in the project |

Create a service account and key if you don't have one:

```bash
gcloud iam service-accounts create fullsend-runner \
  --display-name="Fullsend Runner" \
  --project=<your-gcp-project>

gcloud projects add-iam-policy-binding <your-gcp-project> \
  --member="serviceAccount:fullsend-runner@<your-gcp-project>.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user" \
  --condition=None

gcloud iam service-accounts keys create /tmp/sa-key.json \
  --iam-account=fullsend-runner@<your-gcp-project>.iam.gserviceaccount.com

export GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json
export FULLSEND_GCP_PROJECT_ID=<your-gcp-project>
```

The `fullsend run` CLI must also be installed and in your `$PATH`.

## Steps

### Automated (fullsend run)

1. Navigate to the experiment directory:
   ```bash
   cd experiments/host-side-api-server
   ```

2. Run the setup script to build Go binaries and verify prerequisites:
   ```bash
   ./setup.sh
   ```

3. Run a harness:
   ```bash
   ./run.sh baked-instructions-full
   ```

   Available harnesses (3 discovery methods × 2 policies):
   - `baked-instructions-full` / `baked-instructions-restricted`
   - `openapi-discovery-full` / `openapi-discovery-restricted`
   - `tooluse-discovery-full` / `tooluse-discovery-restricted`

4. Results are saved to `results/`.

## Expected Output

- Both API servers start and pass health checks
- Sandbox is created with L7 policy applied
- From inside the sandbox, `curl` to API server endpoints succeeds for
  allowed endpoints and returns 403 for restricted ones
- Container build via host API completes successfully
- Repo provisioning clones, scans, and reports results
