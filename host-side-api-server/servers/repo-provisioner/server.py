#!/usr/bin/env python3
"""Repo provisioner server.

Clones repos, scans them for security issues, and uploads clean repos into
an OpenShell sandbox via `openshell sandbox upload`. Follows the uniform
process contract: --port, --token, --sandbox, /healthz, SIGTERM.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

bearer_token: str = ""
config: dict = {}
sandbox_name: str = ""
# In-memory store of provisioning operations keyed by id.
operations: dict = {}
operations_lock = threading.Lock()

PREFIX = "[repo-provisioner]"


def log(msg: str) -> None:
    print(f"{PREFIX} {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Security scanning
# ---------------------------------------------------------------------------

PROMPT_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+(\w+\s+)?mode", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"IMPORTANT:\s*ignore", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
]

TEXT_EXTENSIONS: set[str] = {
    ".md", ".txt", ".rst", ".adoc", ".html",
    ".json", ".yaml", ".yml", ".toml",
}

CONFIG_DIRS: set[str] = {".github", ".gitlab", ".vscode", ".idea"}

ELF_MAGIC = b"\x7fELF"
MACHO_MAGICS = {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"}


def scan_repo(repo_dir: str) -> list[dict]:
    """Scan a cloned repo for security issues.

    Returns a list of finding dicts: {file, issue, severity}.
    """
    findings: list[dict] = []

    for root, dirs, files in os.walk(repo_dir):
        # Skip .git internals except .git/hooks
        rel_root = os.path.relpath(root, repo_dir)

        # --- Git hooks with executable content ---
        if rel_root == os.path.join(".git", "hooks") or rel_root.startswith(os.path.join(".git", "hooks") + os.sep):
            for fname in files:
                if fname.endswith(".sample"):
                    continue
                fpath = os.path.join(root, fname)
                if os.access(fpath, os.X_OK):
                    findings.append({
                        "file": os.path.relpath(fpath, repo_dir),
                        "issue": "Executable git hook",
                        "severity": "medium",
                    })

        # Skip the rest of .git
        if rel_root == ".git" or rel_root.startswith(".git" + os.sep):
            continue

        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_dir)

            # --- Symlinks pointing outside repo ---
            if os.path.islink(fpath):
                target = os.path.realpath(fpath)
                repo_real = os.path.realpath(repo_dir)
                if not target.startswith(repo_real + os.sep) and target != repo_real:
                    findings.append({
                        "file": rel_path,
                        "issue": f"Symlink points outside repo: {target}",
                        "severity": "high",
                    })

            # --- Prompt injection patterns in text files ---
            _, ext = os.path.splitext(fname)
            if ext.lower() in TEXT_EXTENSIONS:
                try:
                    with open(fpath, "r", errors="replace") as f:
                        content = f.read()
                    for pattern in PROMPT_INJECTION_PATTERNS:
                        for match in pattern.finditer(content):
                            findings.append({
                                "file": rel_path,
                                "issue": f"Prompt injection pattern: {match.group()}",
                                "severity": "medium",
                            })
                except OSError:
                    pass

            # --- Suspicious binaries in config directories ---
            parts = rel_path.split(os.sep)
            if len(parts) >= 2 and parts[0] in CONFIG_DIRS:
                try:
                    with open(fpath, "rb") as f:
                        header = f.read(4)
                    if header == ELF_MAGIC:
                        findings.append({
                            "file": rel_path,
                            "issue": "ELF binary in config directory",
                            "severity": "medium",
                        })
                    elif header in MACHO_MAGICS:
                        findings.append({
                            "file": rel_path,
                            "issue": "Mach-O binary in config directory",
                            "severity": "medium",
                        })
                except OSError:
                    pass

    return findings


# ---------------------------------------------------------------------------
# Provisioning logic
# ---------------------------------------------------------------------------

def clone_repo(repo: str, ref: str, dest: str) -> None:
    """Clone a GitHub repo into dest, checking out ref."""
    github_token = config.get("github_token", "")
    if github_token:
        clone_url = f"https://x-access-token:{github_token}@github.com/{repo}.git"
    else:
        clone_url = f"https://github.com/{repo}.git"

    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, clone_url, dest],
        check=True,
        capture_output=True,
        text=True,
    )


def upload_to_sandbox_named(sb: str, local_path: str, dest: str) -> None:
    """Upload files into the sandbox via openshell sandbox upload."""
    cmd = ["openshell", "sandbox", "upload", sb, local_path]
    if dest:
        cmd.append(dest)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr,
        )


def provision(repo: str, ref: str, dest: str = "", sandbox: str = "") -> dict:
    """Run the full provisioning flow and return the operation result."""
    op_id = str(uuid.uuid4())
    sb = sandbox or sandbox_name
    with operations_lock:
        operations[op_id] = {"id": op_id, "status": "in_progress", "repo": repo, "ref": ref}

    try:
        with tempfile.TemporaryDirectory(prefix="repo-prov-") as tmpdir:
            clone_dest = os.path.join(tmpdir, "repo")

            # Clone
            log(f"Cloning {repo}@{ref}")
            clone_repo(repo, ref, clone_dest)

            # Scan
            log(f"Scanning {repo}")
            findings = scan_repo(clone_dest)
            high_findings = [f for f in findings if f["severity"] == "high"]

            if high_findings:
                result = {
                    "id": op_id,
                    "status": "rejected",
                    "repo": repo,
                    "ref": ref,
                    "findings": findings,
                }
                with operations_lock:
                    operations[op_id] = result
                log(f"Rejected {repo}: {len(high_findings)} high-severity finding(s)")
                return result

            # Upload into sandbox
            if sb and dest:
                log(f"Uploading {repo} into sandbox {sb} at {dest}")
                upload_to_sandbox_named(sb, clone_dest, dest)

            result = {
                "id": op_id,
                "status": "completed",
                "repo": repo,
                "ref": ref,
                "findings": findings,
            }
            if dest:
                result["dest"] = dest
            with operations_lock:
                operations[op_id] = result
            log(f"Provisioned {repo} successfully")
            return result

    except subprocess.CalledProcessError as exc:
        result = {
            "id": op_id,
            "status": "failed",
            "repo": repo,
            "ref": ref,
            "error": exc.stderr or str(exc),
            "findings": [],
        }
        with operations_lock:
            operations[op_id] = result
        log(f"Failed to provision {repo}: {exc}")
        return result
    except Exception as exc:
        result = {
            "id": op_id,
            "status": "failed",
            "repo": repo,
            "ref": ref,
            "error": str(exc),
            "findings": [],
        }
        with operations_lock:
            operations[op_id] = result
        log(f"Failed to provision {repo}: {exc}")
        return result


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class RepoProvisionerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the repo provisioner."""

    def log_message(self, format, *args):
        """Override to use stderr with our prefix."""
        log(format % args)

    # --- Auth ---

    def _check_auth(self) -> bool:
        """Validate bearer token. Sends 401 and returns False on failure."""
        auth = self.headers.get("Authorization", "")
        if not auth:
            self._json_response(401, {"error": "missing authorization header"})
            return False
        parts = auth.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer" or parts[1] != bearer_token:
            self._json_response(401, {"error": "invalid token"})
            return False
        return True

    # --- Response helpers ---

    def _json_response(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._json_response(400, {"error": "empty request body"})
            return None
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            self._json_response(400, {"error": f"invalid JSON: {exc}"})
            return None

    # --- Route dispatch ---

    def do_GET(self):
        if self.path == "/healthz":
            self._handle_healthz()
        elif self.path == "/openapi.json":
            self._handle_openapi()
        elif self.path == "/tools.json":
            self._handle_tools()
        elif self.path.startswith("/repo/status/"):
            self._handle_status()
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/repo/provision":
            self._handle_provision()
        else:
            self._json_response(404, {"error": "not found"})

    # --- Endpoint handlers ---

    def _handle_healthz(self):
        self._json_response(200, {"status": "ok"})

    def _handle_provision(self):
        if not self._check_auth():
            return

        body = self._read_json_body()
        if body is None:
            return

        repo = body.get("repo", "")
        ref = body.get("ref", "main")
        dest = body.get("dest", "")
        sandbox = body.get("sandbox", "")

        if not repo or "/" not in repo:
            self._json_response(400, {"error": "repo must be in org/name format"})
            return

        result = provision(repo, ref, dest, sandbox)
        status_code = 200 if result["status"] in ("completed", "rejected") else 500
        self._json_response(status_code, result)

    def _handle_status(self):
        if not self._check_auth():
            return

        op_id = self.path[len("/repo/status/"):]
        if not op_id:
            self._json_response(400, {"error": "operation id is required"})
            return

        with operations_lock:
            op = operations.get(op_id)

        if op is None:
            self._json_response(404, {"error": "operation not found"})
            return

        self._json_response(200, op)

    def _handle_openapi(self):
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Repo Provisioner API",
                "version": "1.0.0",
                "description": (
                    "Clones repos, scans them for security issues, and uploads "
                    "clean repos into an OpenShell sandbox."
                ),
            },
            "paths": {
                "/repo/provision": {
                    "post": {
                        "summary": "Provision a repository",
                        "description": (
                            "Clone a GitHub repo, scan it for security issues, "
                            "and upload it into the sandbox if clean."
                        ),
                        "security": [{"bearerAuth": []}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["repo"],
                                        "properties": {
                                            "repo": {
                                                "type": "string",
                                                "description": "GitHub repo in org/name format",
                                            },
                                            "ref": {
                                                "type": "string",
                                                "description": "Git ref to check out (default: main)",
                                                "default": "main",
                                            },
                                            "dest": {
                                                "type": "string",
                                                "description": "Sandbox path to upload the cloned repo to",
                                            },
                                            "sandbox": {
                                                "type": "string",
                                                "description": "Sandbox name for uploading the repo (use $(hostname | sed 's/^sandbox-//') from inside the sandbox)",
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Provisioning result",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "status": {
                                                    "type": "string",
                                                    "enum": ["completed", "rejected", "failed"],
                                                },
                                                "repo": {"type": "string"},
                                                "ref": {"type": "string"},
                                                "findings": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "file": {"type": "string"},
                                                            "issue": {"type": "string"},
                                                            "severity": {
                                                                "type": "string",
                                                                "enum": ["high", "medium"],
                                                            },
                                                        },
                                                    },
                                                },
                                                "error": {"type": "string"},
                                            },
                                        }
                                    }
                                },
                            },
                            "401": {
                                "description": "Missing or invalid bearer token",
                            },
                        },
                    }
                },
                "/repo/status/{id}": {
                    "get": {
                        "summary": "Check provisioning operation status",
                        "description": "Retrieve the status and results of a provisioning operation by its ID.",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "Provisioning operation ID",
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Operation status",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "status": {"type": "string"},
                                                "repo": {"type": "string"},
                                                "ref": {"type": "string"},
                                                "findings": {"type": "array"},
                                                "error": {"type": "string"},
                                            },
                                        }
                                    }
                                },
                            },
                            "404": {
                                "description": "Operation not found",
                            },
                            "401": {
                                "description": "Missing or invalid bearer token",
                            },
                        },
                    }
                },
            },
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                    }
                }
            },
        }
        self._json_response(200, spec)

    def _handle_tools(self):
        tools = [
            {
                "name": "provision_repo",
                "description": (
                    "Clone a GitHub repository, scan it for security issues "
                    "(git hooks, symlinks, prompt injection, suspicious binaries), "
                    "and upload it into the sandbox if clean."
                ),
                "endpoint": "/repo/provision",
                "method": "POST",
                "input_schema": {
                    "type": "object",
                    "required": ["repo"],
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "GitHub repo in org/name format",
                        },
                        "ref": {
                            "type": "string",
                            "description": "Git ref to check out (default: main)",
                            "default": "main",
                        },
                        "dest": {
                            "type": "string",
                            "description": "Sandbox path to upload the cloned repo to. If omitted, the repo is only scanned but not uploaded.",
                        },
                        "sandbox": {
                            "type": "string",
                            "description": "Sandbox name for uploading the repo. Use $(hostname) from inside the sandbox.",
                        },
                    },
                },
            },
            {
                "name": "check_provision_status",
                "description": "Check the status of a provisioning operation by its ID.",
                "endpoint": "/repo/status/{id}",
                "method": "GET",
                "input_schema": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Provisioning operation ID returned by provision_repo",
                        },
                    },
                },
            },
        ]
        self._json_response(200, tools)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def run_server(port: int) -> None:
    server = HTTPServer(("", port), RepoProvisionerHandler)
    log(f"Starting repo provisioner server on port {port}")

    # Graceful shutdown on SIGTERM / SIGINT
    def shutdown_handler(signum, frame):
        log("Shutting down server...")
        # Shut down in a thread to avoid deadlock when signal arrives
        # during server_forever's select().
        threading.Thread(target=server.shutdown).start()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    server.serve_forever()
    log("Server stopped")


def main():
    global bearer_token, config, sandbox_name

    parser = argparse.ArgumentParser(description="Repo provisioner server")
    parser.add_argument("--port", type=int, default=9091, help="Port to listen on")
    parser.add_argument("--token", required=True, help="Bearer token for authentication")
    parser.add_argument("--sandbox", default="", help="OpenShell sandbox name for uploading repos")
    parser.add_argument("--config", default="", help="Path to optional config JSON file")
    args = parser.parse_args()

    bearer_token = args.token
    sandbox_name = args.sandbox

    if args.config:
        with open(args.config) as f:
            config = json.load(f)
        log(f"Loaded config from {args.config}")

    run_server(args.port)


if __name__ == "__main__":
    main()
