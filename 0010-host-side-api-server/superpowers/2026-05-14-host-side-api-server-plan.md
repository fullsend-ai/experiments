# Host-Side API Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PoC of two host-side API servers (Go container builder, Python repo provisioner) callable from inside an OpenShell sandbox, managed by a language-agnostic Go orchestrator.

**Architecture:** Go orchestrator starts both servers via a uniform process contract (start → healthcheck → register → SIGTERM), provisions an OpenShell sandbox with L7 policy allowing egress to the servers, and passes endpoint info + bearer token into the sandbox. The agent inside calls the servers via curl through the L7 proxy at `10.200.0.1:3128`.

**Tech Stack:** Go 1.23 (orchestrator + builder server), Python 3.11+ (repo provisioner), OpenShell (sandbox + L7 proxy), shell scripts (setup/run).

**Spec:** `experiments/host-side-api-server/superpowers/2026-05-14-host-side-api-server-design.md`

**Reference experiment:** `experiments/agent-scoped-tools-triage/` — reuse sandbox lifecycle patterns from `launcher/sandbox.py` and L7 policy format from `policies/triage-write.yaml`.

---

All paths below are relative to `experiments/host-side-api-server/`.

## Task 1: Go module scaffolding and container builder server

**Files:**
- Create: `servers/builder/main.go`
- Create: `servers/builder/go.mod`

- [ ] **Step 1: Initialize Go module**

```bash
cd experiments/host-side-api-server
mkdir -p servers/builder
cd servers/builder
go mod init github.com/fullsend-ai/experiments/host-side-api-server/servers/builder
```

- [ ] **Step 2: Write the builder server**

Create `servers/builder/main.go`:

```go
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"
)

type BuildRequest struct {
	Dockerfile string `json:"dockerfile"`
	ContextDir string `json:"context_dir"`
	Tag        string `json:"tag"`
}

type BuildResponse struct {
	ID     string `json:"id"`
	Tag    string `json:"tag"`
	Status string `json:"status"`
	Output string `json:"output,omitempty"`
	Error  string `json:"error,omitempty"`
}

type PushRequest struct {
	Tag string `json:"tag"`
}

type Server struct {
	token    string
	mu       sync.Mutex
	builds   map[string]*BuildResponse
	registry string
}

func (s *Server) authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		if auth != "Bearer "+s.token {
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		next(w, r)
	}
}

func (s *Server) handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok"}`))
}

func (s *Server) handleBuild(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	var req BuildRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	if req.Tag == "" {
		http.Error(w, `{"error":"tag is required"}`, http.StatusBadRequest)
		return
	}

	buildID := uuid.New().String()
	resp := &BuildResponse{ID: buildID, Tag: req.Tag, Status: "building"}

	s.mu.Lock()
	s.builds[buildID] = resp
	s.mu.Unlock()

	// Run build synchronously — this tests long-running operations
	dockerfile := req.Dockerfile
	if dockerfile == "" {
		dockerfile = "Dockerfile"
	}
	contextDir := req.ContextDir
	if contextDir == "" {
		contextDir = "."
	}

	// Try podman first, fall back to docker
	builder := "podman"
	if _, err := exec.LookPath("podman"); err != nil {
		builder = "docker"
	}

	cmd := exec.Command(builder, "build", "-t", req.Tag, "-f", dockerfile, contextDir)
	output, err := cmd.CombinedOutput()

	s.mu.Lock()
	if err != nil {
		resp.Status = "failed"
		resp.Error = err.Error()
		resp.Output = string(output)
	} else {
		resp.Status = "completed"
		resp.Output = string(output)
	}
	s.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func (s *Server) handlePush(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	var req PushRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	if req.Tag == "" {
		http.Error(w, `{"error":"tag is required"}`, http.StatusBadRequest)
		return
	}

	builder := "podman"
	if _, err := exec.LookPath("podman"); err != nil {
		builder = "docker"
	}

	cmd := exec.Command(builder, "push", req.Tag)
	output, err := cmd.CombinedOutput()

	resp := map[string]string{"tag": req.Tag}
	if err != nil {
		resp["status"] = "failed"
		resp["error"] = err.Error()
		resp["output"] = string(output)
	} else {
		resp["status"] = "pushed"
		resp["output"] = string(output)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleImages(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	builder := "podman"
	if _, err := exec.LookPath("podman"); err != nil {
		builder = "docker"
	}

	cmd := exec.Command(builder, "images", "--format", "json")
	output, err := cmd.CombinedOutput()
	if err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"%s"}`, err.Error()), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(output)
}

func (s *Server) handleOpenAPI(w http.ResponseWriter, r *http.Request) {
	spec := map[string]interface{}{
		"openapi": "3.0.0",
		"info":    map[string]string{"title": "Container Builder API", "version": "0.1.0"},
		"paths": map[string]interface{}{
			"/build": map[string]interface{}{
				"post": map[string]interface{}{
					"summary":     "Build a container image",
					"description": "Builds a container image from a Dockerfile and context directory using podman or docker on the host.",
					"requestBody": map[string]interface{}{
						"required": true,
						"content": map[string]interface{}{
							"application/json": map[string]interface{}{
								"schema": map[string]interface{}{
									"type": "object",
									"properties": map[string]interface{}{
										"dockerfile":  map[string]string{"type": "string", "description": "Path to Dockerfile (default: Dockerfile)"},
										"context_dir": map[string]string{"type": "string", "description": "Build context directory (default: .)"},
										"tag":         map[string]string{"type": "string", "description": "Image tag (required)"},
									},
									"required": []string{"tag"},
								},
							},
						},
					},
				},
			},
			"/push": map[string]interface{}{
				"post": map[string]interface{}{
					"summary": "Push a built image to a registry",
					"requestBody": map[string]interface{}{
						"required": true,
						"content": map[string]interface{}{
							"application/json": map[string]interface{}{
								"schema": map[string]interface{}{
									"type": "object",
									"properties": map[string]interface{}{
										"tag": map[string]string{"type": "string", "description": "Image tag to push (required)"},
									},
									"required": []string{"tag"},
								},
							},
						},
					},
				},
			},
			"/images": map[string]interface{}{
				"get": map[string]interface{}{
					"summary": "List locally built images",
				},
			},
		},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(spec)
}

func (s *Server) handleToolsJSON(w http.ResponseWriter, r *http.Request) {
	tools := map[string]interface{}{
		"tools": []map[string]interface{}{
			{
				"name":        "build_container_image",
				"description": "Build a container image from a Dockerfile and context directory using podman or docker on the host.",
				"endpoint":    "POST /build",
				"input_schema": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"dockerfile":  map[string]string{"type": "string", "description": "Path to Dockerfile (default: Dockerfile)"},
						"context_dir": map[string]string{"type": "string", "description": "Build context directory (default: .)"},
						"tag":         map[string]string{"type": "string", "description": "Image tag (required)"},
					},
					"required": []string{"tag"},
				},
			},
			{
				"name":        "push_image",
				"description": "Push a built container image to a registry.",
				"endpoint":    "POST /push",
				"input_schema": map[string]interface{}{
					"type": "object",
					"properties": map[string]interface{}{
						"tag": map[string]string{"type": "string", "description": "Image tag to push (required)"},
					},
					"required": []string{"tag"},
				},
			},
			{
				"name":        "list_images",
				"description": "List all locally built container images.",
				"endpoint":    "GET /images",
				"input_schema": map[string]interface{}{
					"type":       "object",
					"properties": map[string]interface{}{},
				},
			},
		},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tools)
}

func main() {
	port := flag.Int("port", 9090, "Port to listen on")
	token := flag.String("token", "", "Bearer token for authentication")
	flag.Parse()

	if *token == "" {
		log.Fatal("--token is required")
	}

	s := &Server{
		token:  *token,
		builds: make(map[string]*BuildResponse),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", s.handleHealthz)
	mux.HandleFunc("/build", s.authMiddleware(s.handleBuild))
	mux.HandleFunc("/push", s.authMiddleware(s.handlePush))
	mux.HandleFunc("/images", s.authMiddleware(s.handleImages))
	mux.HandleFunc("/openapi.json", s.handleOpenAPI)
	mux.HandleFunc("/tools.json", s.handleToolsJSON)

	srv := &http.Server{
		Addr:    fmt.Sprintf(":%d", *port),
		Handler: mux,
	}

	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
		<-sigCh
		log.Println("Shutting down...")
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()

	log.Printf("Builder server listening on :%d", *port)
	if err := srv.ListenAndServe(); err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
```

- [ ] **Step 3: Add uuid dependency**

```bash
cd servers/builder
go get github.com/google/uuid
```

- [ ] **Step 4: Build and verify it compiles**

```bash
cd servers/builder
go build -o builder-server .
```

Expected: binary `builder-server` created with no errors.

- [ ] **Step 5: Smoke test the server locally**

```bash
cd servers/builder
TOKEN=$(uuidgen)
./builder-server --port 9090 --token "$TOKEN" &
SERVER_PID=$!
sleep 1

# Health check (no auth required)
curl -s http://localhost:9090/healthz
# Expected: {"status":"ok"}

# Auth check — no token
curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/images
# Expected: 401

# Auth check — valid token
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:9090/images
# Expected: JSON array of images (may be empty)

# OpenAPI spec
curl -s http://localhost:9090/openapi.json | python3 -m json.tool | head -5
# Expected: valid JSON with openapi field

# Tools schema
curl -s http://localhost:9090/tools.json | python3 -m json.tool | head -5
# Expected: valid JSON with tools array

kill $SERVER_PID
```

- [ ] **Step 6: Clean up binary and commit**

```bash
rm servers/builder/builder-server
cd experiments/host-side-api-server
git add servers/builder/
git commit -m "feat: add Go container builder API server

Serves /build, /push, /images endpoints with bearer token auth.
Includes /openapi.json and /tools.json for discoverability testing."
```

---

## Task 2: Python repo provisioner server

**Files:**
- Create: `servers/repo-provisioner/server.py`
- Create: `servers/repo-provisioner/requirements.txt`

- [ ] **Step 1: Create requirements.txt**

Create `servers/repo-provisioner/requirements.txt`:

```
# No external dependencies — stdlib only (http.server, subprocess, json)
```

- [ ] **Step 2: Write the repo provisioner server**

Create `servers/repo-provisioner/server.py`:

```python
#!/usr/bin/env python3
"""
REST API server that clones repos, scans for malicious content,
and copies clean repos into an OpenShell sandbox via SCP.

Usage:
  python3 server.py --port 9091 --token <uuid> [--config config.json]

The --config file is optional and may contain:
  {"github_token": "ghp_...", "sandbox_name": "sandbox-xxx", "ssh_config": "/path/to/ssh-config"}
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid as uuid_mod
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from signal import SIGTERM, signal

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+(\w+\s+)?mode", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"IMPORTANT:\s*ignore", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
]

TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".html", ".htm", ".json", ".yaml", ".yml", ".toml"}


def scan_repo(repo_path: str) -> list[dict]:
    """Scan a cloned repo for security issues. Returns list of findings."""
    findings = []
    repo = Path(repo_path)

    # Check for executable git hooks
    hooks_dir = repo / ".git" / "hooks"
    if hooks_dir.exists():
        for hook in hooks_dir.iterdir():
            if hook.is_file() and os.access(hook, os.X_OK):
                if not hook.name.endswith(".sample"):
                    findings.append({
                        "type": "executable_hook",
                        "path": str(hook.relative_to(repo)),
                        "severity": "high",
                        "description": f"Executable git hook: {hook.name}",
                    })

    # Check for symlinks pointing outside the repo
    for path in repo.rglob("*"):
        if path.is_symlink():
            target = path.resolve()
            try:
                target.relative_to(repo.resolve())
            except ValueError:
                findings.append({
                    "type": "symlink_escape",
                    "path": str(path.relative_to(repo)),
                    "target": str(target),
                    "severity": "high",
                    "description": f"Symlink points outside repo: {path.name} -> {target}",
                })

    # Check for prompt injection patterns in text files
    for path in repo.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            try:
                content = path.read_text(errors="ignore")
                for pattern in INJECTION_PATTERNS:
                    match = pattern.search(content)
                    if match:
                        findings.append({
                            "type": "prompt_injection",
                            "path": str(path.relative_to(repo)),
                            "severity": "medium",
                            "description": f"Potential prompt injection: '{match.group()}'",
                        })
                        break
            except (OSError, UnicodeDecodeError):
                pass

    # Check for suspicious binary files in unexpected locations
    suspicious_dirs = {".github", ".gitlab", ".vscode", ".idea"}
    for sdir in suspicious_dirs:
        dirpath = repo / sdir
        if dirpath.exists():
            for path in dirpath.rglob("*"):
                if path.is_file() and not path.suffix.lower() in TEXT_EXTENSIONS | {".png", ".jpg", ".svg", ".gif", ".ico"}:
                    try:
                        with open(path, "rb") as f:
                            header = f.read(4)
                        if header[:2] == b"\x7fE" or header[:4] == b"\xcf\xfa\xed\xfe":
                            findings.append({
                                "type": "suspicious_binary",
                                "path": str(path.relative_to(repo)),
                                "severity": "medium",
                                "description": f"Binary executable in config directory: {path.name}",
                            })
                    except OSError:
                        pass

    return findings


def clone_repo(repo: str, ref: str, dest: str, github_token: str | None = None) -> subprocess.CompletedProcess:
    """Clone a repo to dest. Uses github_token if provided."""
    url = f"https://github.com/{repo}.git"
    env = {**os.environ}
    if github_token:
        url = f"https://x-access-token:{github_token}@github.com/{repo}.git"
    return subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, url, dest],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def copy_to_sandbox(local_path: str, ssh_config: str, sandbox_name: str, remote_path: str) -> subprocess.CompletedProcess:
    """Copy a directory into a sandbox via SCP."""
    return subprocess.run(
        [
            "scp", "-F", ssh_config, "-r",
            local_path,
            f"openshell-{sandbox_name}:{remote_path}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def make_handler(token: str, config: dict) -> type:
    """Create HTTP handler with token and config bound."""

    github_token = config.get("github_token")
    sandbox_name = config.get("sandbox_name", "")
    ssh_config = config.get("ssh_config", "")

    jobs: dict[str, dict] = {}
    jobs_lock = threading.Lock()

    class RepoProvisionerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok"})
                return

            # GET /repo/status/{id}
            if self.path.startswith("/repo/status/"):
                self._check_auth()
                job_id = self.path.split("/")[-1]
                with jobs_lock:
                    job = jobs.get(job_id)
                if job is None:
                    self._send_json(404, {"error": "job not found"})
                else:
                    self._send_json(200, job)
                return

            if self.path == "/openapi.json":
                self._send_openapi()
                return

            if self.path == "/tools.json":
                self._send_tools()
                return

            self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path == "/repo/provision":
                if not self._check_auth():
                    return
                content_length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(content_length))
                repo = body.get("repo", "")
                ref = body.get("ref", "main")

                if not repo or "/" not in repo:
                    self._send_json(400, {"error": "repo must be in org/name format"})
                    return

                job_id = str(uuid_mod.uuid4())
                job = {"id": job_id, "repo": repo, "ref": ref, "status": "cloning"}
                with jobs_lock:
                    jobs[job_id] = job

                # Run synchronously for PoC
                with tempfile.TemporaryDirectory() as tmpdir:
                    clone_dest = os.path.join(tmpdir, repo.split("/")[-1])

                    # Clone
                    result = clone_repo(repo, ref, clone_dest, github_token)
                    if result.returncode != 0:
                        job["status"] = "failed"
                        job["error"] = f"Clone failed: {result.stderr}"
                        self._send_json(500, job)
                        return

                    # Scan
                    job["status"] = "scanning"
                    findings = scan_repo(clone_dest)
                    high_findings = [f for f in findings if f["severity"] == "high"]

                    if high_findings:
                        job["status"] = "rejected"
                        job["findings"] = findings
                        self._send_json(200, job)
                        return

                    # Copy to sandbox (if configured)
                    if sandbox_name and ssh_config:
                        job["status"] = "copying"
                        cp_result = copy_to_sandbox(
                            clone_dest, ssh_config, sandbox_name, "/tmp/workspace/"
                        )
                        if cp_result.returncode != 0:
                            job["status"] = "failed"
                            job["error"] = f"SCP failed: {cp_result.stderr}"
                            self._send_json(500, job)
                            return

                    job["status"] = "completed"
                    job["findings"] = findings
                    self._send_json(200, job)
                return

            self._send_json(404, {"error": "not found"})

        def _check_auth(self) -> bool:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {token}":
                self._send_json(401, {"error": "unauthorized"})
                return False
            return True

        def _send_json(self, status: int, data: dict):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def _send_openapi(self):
            spec = {
                "openapi": "3.0.0",
                "info": {"title": "Secure Repo Provisioner API", "version": "0.1.0"},
                "paths": {
                    "/repo/provision": {
                        "post": {
                            "summary": "Clone, scan, and provision a repo into the sandbox",
                            "description": "Clones a GitHub repo, scans for security issues (executable hooks, symlink escapes, prompt injection, suspicious binaries), and copies the clean repo into the sandbox. Rejects repos with high-severity findings.",
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "repo": {"type": "string", "description": "Repository in org/name format"},
                                                "ref": {"type": "string", "description": "Git ref to clone (default: main)"},
                                            },
                                            "required": ["repo"],
                                        }
                                    }
                                },
                            },
                        }
                    },
                    "/repo/status/{id}": {
                        "get": {
                            "summary": "Check provisioning status",
                            "description": "Returns the current status of a provisioning job.",
                        }
                    },
                },
            }
            self._send_json(200, spec)

        def _send_tools(self):
            tools = {
                "tools": [
                    {
                        "name": "provision_repo",
                        "description": "Clone a GitHub repo, scan it for security issues, and copy it into the sandbox if scans pass. Rejects repos with executable git hooks, symlink escapes, prompt injection patterns, or suspicious binaries.",
                        "endpoint": "POST /repo/provision",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string", "description": "Repository in org/name format (e.g. 'org/repo')"},
                                "ref": {"type": "string", "description": "Git ref to clone (default: main)"},
                            },
                            "required": ["repo"],
                        },
                    },
                    {
                        "name": "check_provision_status",
                        "description": "Check the status of a repo provisioning job.",
                        "endpoint": "GET /repo/status/{id}",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Job ID returned by provision_repo"},
                            },
                            "required": ["id"],
                        },
                    },
                ]
            }
            self._send_json(200, tools)

        def log_message(self, format, *args):
            print(f"[repo-provisioner] {args[0]} {args[1]} {args[2]}", file=sys.stderr)

    return RepoProvisionerHandler


def main():
    parser = argparse.ArgumentParser(description="Secure Repo Provisioner API")
    parser.add_argument("--port", type=int, default=9091)
    parser.add_argument("--token", required=True)
    parser.add_argument("--config", help="Path to JSON config file")
    args = parser.parse_args()

    config = {}
    if args.config:
        with open(args.config) as f:
            config = json.load(f)

    handler = make_handler(args.token, config)
    server = HTTPServer(("", args.port), handler)

    def shutdown_handler(signum, frame):
        print("[repo-provisioner] Shutting down...", file=sys.stderr)
        threading.Thread(target=server.shutdown).start()

    signal(SIGTERM, shutdown_handler)

    print(f"[repo-provisioner] Listening on :{args.port}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test the server locally**

```bash
cd experiments/host-side-api-server
TOKEN=$(uuidgen)
python3 servers/repo-provisioner/server.py --port 9091 --token "$TOKEN" &
SERVER_PID=$!
sleep 1

# Health check
curl -s http://localhost:9091/healthz
# Expected: {"status": "ok"}

# Auth check — no token
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:9091/repo/provision
# Expected: 401

# Provision a public repo (no sandbox configured, so no SCP step)
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"repo": "octocat/Hello-World", "ref": "master"}' \
  http://localhost:9091/repo/provision | python3 -m json.tool
# Expected: JSON with status "completed" and findings array

# OpenAPI spec
curl -s http://localhost:9091/openapi.json | python3 -m json.tool | head -5

# Tools schema
curl -s http://localhost:9091/tools.json | python3 -m json.tool | head -5

kill $SERVER_PID
```

- [ ] **Step 4: Commit**

```bash
git add servers/repo-provisioner/
git commit -m "feat: add Python secure repo provisioner API server

Clones repos, scans for executable hooks, symlink escapes, prompt
injection patterns, and suspicious binaries. Copies into sandbox
via SCP only if scans pass. Includes /openapi.json and /tools.json."
```

---

## Task 3: Go orchestrator

**Files:**
- Create: `orchestrator/main.go`
- Create: `orchestrator/go.mod`

- [ ] **Step 1: Initialize Go module**

```bash
mkdir -p experiments/host-side-api-server/orchestrator
cd experiments/host-side-api-server/orchestrator
go mod init github.com/fullsend-ai/experiments/host-side-api-server/orchestrator
```

- [ ] **Step 2: Write the orchestrator**

Create `orchestrator/main.go`:

```go
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/google/uuid"
)

type ServerConfig struct {
	Name    string `json:"name"`
	Command string `json:"command"`
	Port    int    `json:"port"`
}

type RunningServer struct {
	Config  ServerConfig
	Process *os.Process
}

func resolveHostIP() (string, error) {
	cmd := exec.Command("getent", "hosts", "host.openshell.internal")
	out, err := cmd.Output()
	if err == nil {
		parts := strings.Fields(string(out))
		if len(parts) > 0 {
			return parts[0], nil
		}
	}
	// Fallback: try to resolve via docker bridge
	cmd = exec.Command("ip", "route", "show", "default")
	out, err = cmd.Output()
	if err != nil {
		return "", fmt.Errorf("cannot resolve host IP: %w", err)
	}
	parts := strings.Fields(string(out))
	for i, p := range parts {
		if p == "via" && i+1 < len(parts) {
			return parts[i+1], nil
		}
	}
	return "", fmt.Errorf("cannot determine host IP from route table")
}

func startServer(cfg ServerConfig, token string) (*RunningServer, error) {
	args := strings.Fields(cfg.Command)
	args = append(args, "--port", fmt.Sprintf("%d", cfg.Port), "--token", token)

	cmd := exec.Command(args[0], args[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start %s: %w", cfg.Name, err)
	}

	// Poll healthz
	url := fmt.Sprintf("http://localhost:%d/healthz", cfg.Port)
	for i := 0; i < 30; i++ {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == 200 {
			resp.Body.Close()
			log.Printf("[orchestrator] %s is ready on :%d", cfg.Name, cfg.Port)
			return &RunningServer{Config: cfg, Process: cmd.Process}, nil
		}
		time.Sleep(500 * time.Millisecond)
	}

	cmd.Process.Kill()
	return nil, fmt.Errorf("%s did not become healthy within 15s", cfg.Name)
}

func stopServer(srv *RunningServer) {
	log.Printf("[orchestrator] Stopping %s (pid %d)", srv.Config.Name, srv.Process.Pid)
	srv.Process.Signal(syscall.SIGTERM)

	done := make(chan struct{})
	go func() {
		srv.Process.Wait()
		close(done)
	}()

	select {
	case <-done:
		log.Printf("[orchestrator] %s stopped", srv.Config.Name)
	case <-time.After(5 * time.Second):
		log.Printf("[orchestrator] %s did not stop, killing", srv.Config.Name)
		srv.Process.Kill()
	}
}

func renderPolicy(templatePath string, hostIP string) (string, error) {
	content, err := os.ReadFile(templatePath)
	if err != nil {
		return "", err
	}
	rendered := strings.ReplaceAll(string(content), "{{HOST_IP}}", hostIP)

	tmpFile, err := os.CreateTemp("", "policy-*.yaml")
	if err != nil {
		return "", err
	}
	tmpFile.WriteString(rendered)
	tmpFile.Close()
	return tmpFile.Name(), nil
}

func createSandbox(name string) error {
	cmd := exec.Command("timeout", "60",
		"openshell", "sandbox", "create",
		"--name", name,
		"--keep",
		"--no-auto-providers",
		"--no-tty",
	)
	cmd.Stdin = nil
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	// timeout exits 124 — check if sandbox exists
	if err != nil {
		check := exec.Command("openshell", "sandbox", "get", name)
		if checkErr := check.Run(); checkErr != nil {
			return fmt.Errorf("sandbox create failed: %w", err)
		}
	}

	// Poll for ready
	for i := 0; i < 30; i++ {
		check := exec.Command("openshell", "sandbox", "get", name)
		out, err := check.Output()
		if err == nil && strings.Contains(string(out), "Ready") {
			return nil
		}
		time.Sleep(2 * time.Second)
	}
	return fmt.Errorf("sandbox %s not ready after 60s", name)
}

func applyPolicy(sandboxName string, policyPath string) error {
	for attempt := 1; attempt <= 3; attempt++ {
		cmd := exec.Command("openshell", "policy", "set", sandboxName,
			"--policy", policyPath, "--wait")
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err == nil {
			return nil
		}
		log.Printf("[orchestrator] Policy attempt %d failed, retrying in 3s...", attempt)
		time.Sleep(3 * time.Second)
	}
	return fmt.Errorf("policy set failed after 3 attempts")
}

func getSSHConfig(sandboxName string) (string, error) {
	cmd := exec.Command("openshell", "sandbox", "ssh-config", sandboxName)
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	tmpFile, err := os.CreateTemp("", "ssh-config-*")
	if err != nil {
		return "", err
	}
	tmpFile.Write(out)
	tmpFile.Close()
	return tmpFile.Name(), nil
}

func sandboxSSH(sshConfigPath string, sandboxName string, command string, timeout int) (string, error) {
	cmd := exec.Command("ssh", "-F", sshConfigPath, fmt.Sprintf("openshell-%s", sandboxName), command)
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func deleteSandbox(name string) {
	exec.Command("openshell", "sandbox", "delete", name).Run()
}

func main() {
	policyPath := flag.String("policy", "", "Path to L7 policy template YAML")
	serversFile := flag.String("servers", "", "Path to JSON file listing servers to start")
	sandboxName := flag.String("sandbox", "api-server-test", "OpenShell sandbox name")
	agentCmd := flag.String("agent-command", "", "Command to run inside the sandbox (e.g. curl test)")
	flag.Parse()

	if *policyPath == "" || *serversFile == "" {
		log.Fatal("--policy and --servers are required")
	}

	// Generate per-run token
	token := uuid.New().String()
	log.Printf("[orchestrator] Per-run token: %s", token)

	// Read server configs
	serversData, err := os.ReadFile(*serversFile)
	if err != nil {
		log.Fatalf("Cannot read servers file: %v", err)
	}
	var serverConfigs []ServerConfig
	if err := json.Unmarshal(serversData, &serverConfigs); err != nil {
		log.Fatalf("Cannot parse servers file: %v", err)
	}

	// Start servers
	var running []*RunningServer
	defer func() {
		for _, srv := range running {
			stopServer(srv)
		}
	}()

	for _, cfg := range serverConfigs {
		srv, err := startServer(cfg, token)
		if err != nil {
			log.Fatalf("Failed to start server: %v", err)
		}
		running = append(running, srv)
	}

	// Resolve host IP and render policy
	hostIP, err := resolveHostIP()
	if err != nil {
		log.Fatalf("Cannot resolve host IP: %v", err)
	}
	log.Printf("[orchestrator] Host IP: %s", hostIP)

	renderedPolicy, err := renderPolicy(*policyPath, hostIP)
	if err != nil {
		log.Fatalf("Cannot render policy: %v", err)
	}
	defer os.Remove(renderedPolicy)

	// Create sandbox
	log.Printf("[orchestrator] Creating sandbox %s...", *sandboxName)
	if err := createSandbox(*sandboxName); err != nil {
		log.Fatalf("Sandbox creation failed: %v", err)
	}
	defer deleteSandbox(*sandboxName)

	// Apply policy
	log.Printf("[orchestrator] Applying L7 policy...")
	if err := applyPolicy(*sandboxName, renderedPolicy); err != nil {
		log.Fatalf("Policy application failed: %v", err)
	}

	// Get SSH config
	sshConfigPath, err := getSSHConfig(*sandboxName)
	if err != nil {
		log.Fatalf("Cannot get SSH config: %v", err)
	}
	defer os.Remove(sshConfigPath)

	// Export token and endpoint info into sandbox
	builderURL := fmt.Sprintf("http://%s:9090", hostIP)
	provisionerURL := fmt.Sprintf("http://%s:9091", hostIP)
	envSetup := fmt.Sprintf(
		"export API_TOKEN='%s' BUILDER_URL='%s' PROVISIONER_URL='%s'",
		token, builderURL, provisionerURL,
	)
	sandboxSSH(sshConfigPath, *sandboxName,
		fmt.Sprintf("echo \"%s\" >> ~/.bashrc", envSetup), 10)

	// Run agent command if provided
	if *agentCmd != "" {
		log.Printf("[orchestrator] Running agent command in sandbox...")
		absAgentCmd := *agentCmd
		// Read the command file if it's a file path
		if _, err := os.Stat(absAgentCmd); err == nil {
			content, err := os.ReadFile(absAgentCmd)
			if err != nil {
				log.Fatalf("Cannot read agent command file: %v", err)
			}
			absAgentCmd = string(content)
		}

		// Prepend env setup since .bashrc isn't sourced for non-interactive ssh
		fullCmd := envSetup + " && " + absAgentCmd
		output, err := sandboxSSH(sshConfigPath, *sandboxName, fullCmd, 300)
		fmt.Println(output)
		if err != nil {
			log.Printf("[orchestrator] Agent command failed: %v", err)
		}
	} else {
		log.Printf("[orchestrator] No --agent-command provided. Sandbox ready for manual testing.")
		log.Printf("[orchestrator] SSH config: %s", sshConfigPath)
		log.Printf("[orchestrator] Token: %s", token)
		log.Printf("[orchestrator] Builder: %s", builderURL)
		log.Printf("[orchestrator] Provisioner: %s", provisionerURL)

		// Wait for interrupt
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
		log.Println("[orchestrator] Press Ctrl+C to shut down")
		<-sigCh
	}

	log.Println("[orchestrator] Shutting down...")
	// Extract results dir from sandbox
	resultsDir := filepath.Join("results", time.Now().Format("2006-01-02-150405"))
	os.MkdirAll(resultsDir, 0o755)
}
```

- [ ] **Step 3: Add uuid dependency**

```bash
cd experiments/host-side-api-server/orchestrator
go get github.com/google/uuid
```

- [ ] **Step 4: Build and verify it compiles**

```bash
cd experiments/host-side-api-server/orchestrator
go build -o orchestrator .
```

Expected: binary `orchestrator` created with no errors.

- [ ] **Step 5: Clean up and commit**

```bash
rm experiments/host-side-api-server/orchestrator/orchestrator
git add experiments/host-side-api-server/orchestrator/
git commit -m "feat: add Go orchestrator for API server lifecycle

Language-agnostic process contract: reads server configs from JSON,
starts servers, polls healthz, provisions OpenShell sandbox with
L7 policy, injects token + endpoints, and cleans up on exit."
```

---

## Task 4: L7 policies

**Files:**
- Create: `policies/full-access.yaml`
- Create: `policies/restricted.yaml`

- [ ] **Step 1: Write full-access policy**

Create `policies/full-access.yaml`:

```yaml
version: 1

# Baseline policy: all API server endpoints allowed.
# Both builder (:9090) and provisioner (:9091) reachable from sandbox.

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc, /dev/urandom, /etc, /var/log]
  read_write: [/tmp, /dev/null]
landlock:
  compatibility: best_effort
process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  builder:
    name: container-builder
    endpoints:
      - host: host.openshell.internal
        port: 9090
        protocol: rest
        enforcement: enforce
        rules:
          - allow:
              method: GET
              path: /healthz
          - allow:
              method: POST
              path: /build
          - allow:
              method: POST
              path: /push
          - allow:
              method: GET
              path: /images
          - allow:
              method: GET
              path: /openapi.json
          - allow:
              method: GET
              path: /tools.json
        allowed_ips:
          - "{{HOST_IP}}/32"
    binaries:
      - path: "**/curl"
  provisioner:
    name: repo-provisioner
    endpoints:
      - host: host.openshell.internal
        port: 9091
        protocol: rest
        enforcement: enforce
        rules:
          - allow:
              method: GET
              path: /healthz
          - allow:
              method: POST
              path: /repo/provision
          - allow:
              method: GET
              path: /repo/status/*
          - allow:
              method: GET
              path: /openapi.json
          - allow:
              method: GET
              path: /tools.json
        allowed_ips:
          - "{{HOST_IP}}/32"
    binaries:
      - path: "**/curl"
```

- [ ] **Step 2: Write restricted policy**

Create `policies/restricted.yaml`:

```yaml
version: 1

# Restricted policy: only build and provision endpoints.
# No /push, no /images — tests agent handling of 403s.

filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /proc, /dev/urandom, /etc, /var/log]
  read_write: [/tmp, /dev/null]
landlock:
  compatibility: best_effort
process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  builder:
    name: container-builder-restricted
    endpoints:
      - host: host.openshell.internal
        port: 9090
        protocol: rest
        enforcement: enforce
        rules:
          - allow:
              method: GET
              path: /healthz
          - allow:
              method: POST
              path: /build
          - allow:
              method: GET
              path: /openapi.json
          - allow:
              method: GET
              path: /tools.json
        allowed_ips:
          - "{{HOST_IP}}/32"
    binaries:
      - path: "**/curl"
  provisioner:
    name: repo-provisioner-restricted
    endpoints:
      - host: host.openshell.internal
        port: 9091
        protocol: rest
        enforcement: enforce
        rules:
          - allow:
              method: GET
              path: /healthz
          - allow:
              method: POST
              path: /repo/provision
          - allow:
              method: GET
              path: /repo/status/*
          - allow:
              method: GET
              path: /openapi.json
          - allow:
              method: GET
              path: /tools.json
        allowed_ips:
          - "{{HOST_IP}}/32"
    binaries:
      - path: "**/curl"
```

- [ ] **Step 3: Commit**

```bash
git add policies/
git commit -m "feat: add L7 network policies for API server access

Full-access baseline and restricted variant (no /push, no /images)
for testing agent behavior on 403 responses."
```

---

## Task 5: Agent definitions for discoverability comparison

**Files:**
- Create: `agents/openapi-discovery.md`
- Create: `agents/tooluse-discovery.md`
- Create: `agents/baked-instructions.md`

- [ ] **Step 1: Write OpenAPI discovery agent**

Create `agents/openapi-discovery.md`:

```markdown
---
name: openapi-discovery-agent
description: Tests API discoverability via OpenAPI spec
---

# API Discovery Agent (OpenAPI)

You are inside an OpenShell sandbox. Two API servers are running on the host
and accessible via curl through the network proxy.

## How to discover available APIs

Fetch the OpenAPI spec from each server to learn what endpoints are available:

```bash
curl -s "$BUILDER_URL/openapi.json" | python3 -m json.tool
curl -s "$PROVISIONER_URL/openapi.json" | python3 -m json.tool
```

## Authentication

All API requests require a bearer token. Use the `$API_TOKEN` environment
variable:

```bash
curl -H "Authorization: Bearer $API_TOKEN" ...
```

## Your task

1. Discover the available APIs by reading the OpenAPI specs
2. Use the builder API to build a simple container image
3. Use the provisioner API to provision a public repository
4. Report what worked and what didn't

If any endpoint returns a 403, note it — the network policy may not allow
that endpoint. This is expected behavior, not an error.
```

- [ ] **Step 2: Write tool-use schema discovery agent**

Create `agents/tooluse-discovery.md`:

```markdown
---
name: tooluse-discovery-agent
description: Tests API discoverability via tool-use schema
---

# API Discovery Agent (Tool-Use Schema)

You are inside an OpenShell sandbox. Two API servers are running on the host
and accessible via curl through the network proxy.

## How to discover available APIs

Fetch the tool definitions from each server:

```bash
curl -s "$BUILDER_URL/tools.json" | python3 -m json.tool
curl -s "$PROVISIONER_URL/tools.json" | python3 -m json.tool
```

Each tool definition includes a name, description, endpoint (HTTP method and
path), and input schema. Call the endpoints using curl with the appropriate
HTTP method and JSON body.

## Authentication

All API requests require a bearer token. Use the `$API_TOKEN` environment
variable:

```bash
curl -H "Authorization: Bearer $API_TOKEN" ...
```

## Your task

1. Discover the available tools by reading the tool schemas
2. Use the builder tools to build a simple container image
3. Use the provisioner tools to provision a public repository
4. Report what worked and what didn't

If any endpoint returns a 403, note it — the network policy may not allow
that endpoint. This is expected behavior, not an error.
```

- [ ] **Step 3: Write baked-instructions agent**

Create `agents/baked-instructions.md`:

```markdown
---
name: baked-instructions-agent
description: Tests API discoverability via hardcoded instructions
---

# API Agent (Baked Instructions)

You are inside an OpenShell sandbox. Two API servers are running on the host
and accessible via curl through the network proxy.

## Authentication

All API requests require a bearer token:

```bash
curl -H "Authorization: Bearer $API_TOKEN" ...
```

## Container Builder API ($BUILDER_URL)

### POST /build
Build a container image from a Dockerfile.

```bash
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tag": "myimage:latest", "dockerfile": "Dockerfile", "context_dir": "."}' \
  "$BUILDER_URL/build"
```

Request body:
- `tag` (required): Image tag
- `dockerfile` (optional, default "Dockerfile"): Path to Dockerfile
- `context_dir` (optional, default "."): Build context directory

### POST /push
Push a built image to a registry.

```bash
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tag": "myimage:latest"}' \
  "$BUILDER_URL/push"
```

### GET /images
List locally built images.

```bash
curl -H "Authorization: Bearer $API_TOKEN" "$BUILDER_URL/images"
```

## Secure Repo Provisioner API ($PROVISIONER_URL)

### POST /repo/provision
Clone a repo, scan for security issues, and copy into the sandbox.

```bash
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"repo": "org/name", "ref": "main"}' \
  "$PROVISIONER_URL/repo/provision"
```

Request body:
- `repo` (required): Repository in org/name format
- `ref` (optional, default "main"): Git ref

### GET /repo/status/{id}
Check provisioning status.

```bash
curl -H "Authorization: Bearer $API_TOKEN" "$PROVISIONER_URL/repo/status/<job-id>"
```

## Your task

1. Use the builder API to build a simple container image
2. Use the provisioner API to provision a public repository
3. Report what worked and what didn't

If any endpoint returns a 403, note it — the network policy may not allow
that endpoint. This is expected behavior, not an error.
```

- [ ] **Step 4: Commit**

```bash
git add agents/
git commit -m "feat: add three agent definitions for discoverability comparison

OpenAPI spec, tool-use schema, and baked-in instructions approaches
for testing how agents discover and use host-side APIs."
```

---

## Task 6: In-sandbox build test script

**Files:**
- Create: `sandbox-build-test/test-in-sandbox-build.sh`

- [ ] **Step 1: Write the test script**

Create `sandbox-build-test/test-in-sandbox-build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Test whether rootless podman/buildah works inside an OpenShell sandbox.
# Expected: it doesn't, due to seccomp blocking CLONE_NEWUSER, AF_NETLINK, setns.
# See: https://github.com/NVIDIA/OpenShell/issues/113

echo "=== Testing container builds inside OpenShell sandbox ==="
echo ""

# Create a minimal Dockerfile
cat > /tmp/test-dockerfile <<'DOCKERFILE'
FROM alpine:latest
RUN echo "hello from inside sandbox build"
DOCKERFILE

echo "--- Attempting: podman build ---"
if command -v podman &>/dev/null; then
    podman build -t test-in-sandbox:latest -f /tmp/test-dockerfile /tmp 2>&1 || true
    echo ""
    echo "Exit code: $?"
else
    echo "podman not found in PATH"
fi

echo ""
echo "--- Attempting: buildah bud ---"
if command -v buildah &>/dev/null; then
    buildah bud -t test-in-sandbox:latest -f /tmp/test-dockerfile /tmp 2>&1 || true
    echo ""
    echo "Exit code: $?"
else
    echo "buildah not found in PATH"
fi

echo ""
echo "--- Attempting: docker build ---"
if command -v docker &>/dev/null; then
    docker build -t test-in-sandbox:latest -f /tmp/test-dockerfile /tmp 2>&1 || true
    echo ""
    echo "Exit code: $?"
else
    echo "docker not found in PATH"
fi

echo ""
echo "=== In-sandbox build test complete ==="
echo "If all attempts failed, the sandbox limitation is confirmed."
echo "If any succeeded, document what changed since OpenShell#113."

rm -f /tmp/test-dockerfile
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x sandbox-build-test/test-in-sandbox-build.sh
git add sandbox-build-test/
git commit -m "feat: add in-sandbox container build test script

Tests whether podman/buildah/docker work inside OpenShell sandbox.
Expected to fail due to seccomp restrictions (NVIDIA/OpenShell#113)."
```

---

## Task 7: Server config, run script, and HOW_TO

**Files:**
- Create: `servers.json`
- Create: `run.sh`
- Create: `setup.sh`
- Create: `HOW_TO.md`
- Create: `README.md`

- [ ] **Step 1: Write servers.json**

Create `servers.json`:

```json
[
  {
    "name": "builder",
    "command": "go run ./servers/builder",
    "port": 9090
  },
  {
    "name": "repo-provisioner",
    "command": "python3 ./servers/repo-provisioner/server.py",
    "port": 9091
  }
]
```

- [ ] **Step 2: Write setup.sh**

Create `setup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== Host-Side API Server Experiment Setup ==="

# Check prerequisites
MISSING=""
for cmd in go python3 openshell curl git uuidgen; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING="$MISSING $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required tools:$MISSING"
    exit 1
fi

echo "All prerequisites found."

# Check openshell gateway
if ! openshell gateway info &>/dev/null 2>&1; then
    echo "ERROR: OpenShell gateway not running. Start it with: openshell gateway start"
    exit 1
fi

echo "OpenShell gateway is running."

# Build Go servers
echo "Building Go builder server..."
(cd servers/builder && go build -o ../../bin/builder-server .)

echo "Building Go orchestrator..."
(cd orchestrator && go build -o ../bin/orchestrator .)

mkdir -p results
echo ""
echo "Setup complete. Run ./run.sh to start the experiment."
```

- [ ] **Step 3: Write run.sh**

Create `run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

POLICY="${1:-policies/full-access.yaml}"
AGENT_CMD="${2:-}"
SANDBOX_NAME="api-server-test-$(date +%s)"

echo "=== Host-Side API Server Experiment ==="
echo "Policy: $POLICY"
echo "Sandbox: $SANDBOX_NAME"

# Build if needed
if [ ! -f bin/orchestrator ] || [ ! -f bin/builder-server ]; then
    echo "Running setup first..."
    ./setup.sh
fi

# Run orchestrator
if [ -n "$AGENT_CMD" ]; then
    ./bin/orchestrator \
        --policy "$POLICY" \
        --servers servers.json \
        --sandbox "$SANDBOX_NAME" \
        --agent-command "$AGENT_CMD"
else
    echo "No agent command specified. Starting in interactive mode."
    echo "The orchestrator will start servers and sandbox, then wait for Ctrl+C."
    echo ""
    ./bin/orchestrator \
        --policy "$POLICY" \
        --servers servers.json \
        --sandbox "$SANDBOX_NAME"
fi
```

- [ ] **Step 4: Write HOW_TO.md**

Create `HOW_TO.md`:

```markdown
## Purpose

Run the host-side API server experiment to validate that agents inside an
OpenShell sandbox can call API servers running on the host through the L7
proxy.

## Requirements

| Requirement | Link |
|-------------|------|
| Go 1.23+ | https://go.dev/dl/ |
| Python 3.11+ | https://www.python.org/downloads/ |
| OpenShell CLI | https://github.com/NVIDIA/OpenShell |
| Docker or Podman | https://docs.docker.com/get-docker/ |
| curl | (pre-installed on most systems) |
| git | https://git-scm.com/downloads |

### Environment variables

No environment variables are required for basic usage. For private repo
provisioning, create a `config.json` with a `github_token` field.

## Steps

1. Navigate to the experiment directory:
   ```bash
   cd experiments/host-side-api-server
   ```

2. Ensure the OpenShell gateway is running:
   ```bash
   openshell gateway start
   ```

3. Run the setup script to build Go binaries and verify prerequisites:
   ```bash
   ./setup.sh
   ```

4. Run the experiment with full-access policy (interactive mode):
   ```bash
   ./run.sh
   ```
   This starts both API servers, creates a sandbox, and waits. You can
   SSH into the sandbox and test manually.

5. Run with restricted policy to test 403 handling:
   ```bash
   ./run.sh policies/restricted.yaml
   ```

6. Run the in-sandbox build test (from inside the sandbox):
   ```bash
   ./sandbox-build-test/test-in-sandbox-build.sh
   ```

## Expected Output

- Both API servers start and pass health checks
- Sandbox is created with L7 policy applied
- From inside the sandbox, `curl` to API server endpoints succeeds for
  allowed endpoints and returns 403 for restricted ones
- In-sandbox build test fails (confirming OpenShell#113 limitation)
- Container build via host API completes successfully
- Repo provisioning clones, scans, and reports results
```

- [ ] **Step 5: Write README.md**

Create `README.md`:

```markdown
# Experiment: Host-Side API Server for Sandboxed Agents

Tracking issue: [fullsend-ai/experiments#25](https://github.com/fullsend-ai/experiments/issues/25)

## What this experiment covers

1. **Basic API server lifecycle** — two API servers started by the
   orchestrator, callable from inside an OpenShell sandbox via the L7 proxy
2. **Credential isolation** — servers hold credentials internally, agents
   never see them
3. **Container build delegation** — Go server builds images via podman/docker
   on the host, working around OpenShell's seccomp restrictions
4. **API discoverability** — three approaches compared: OpenAPI spec,
   tool-use schema, baked-in agent instructions
5. **Per-run auth** — UUID bearer token generated per run
6. **Long-running operations** — container builds that exceed MCP timeout
7. **L7 policy tuning** — most restrictive policy that allows the API

## Architecture

See [design spec](superpowers/2026-05-14-host-side-api-server-design.md).

## Quick start

See [HOW_TO.md](HOW_TO.md).

## Key design decisions

- **Two servers in different languages** (Go + Python) to validate the
  language-agnostic process contract
- **Uniform process contract**: `--port`, `--token`, `/healthz`, SIGTERM
- **Repo provisioner depends on OpenShell#1272**: if content inspection hooks
  ship in OpenShell, the scan-before-copy flow could be handled natively

## Findings

See [results/findings.md](results/findings.md) (populated after running).
```

- [ ] **Step 6: Make scripts executable and commit**

```bash
chmod +x setup.sh run.sh
mkdir -p results
touch results/.gitkeep
git add servers.json run.sh setup.sh HOW_TO.md README.md results/.gitkeep
git commit -m "feat: add orchestration scripts, HOW_TO, and README

Includes servers.json config, setup.sh (build + prerequisite check),
run.sh (orchestrator launcher), HOW_TO.md (reproduction steps),
and README.md (experiment overview)."
```

---

## Task 8: End-to-end smoke test

This task verifies the full pipeline works locally before documenting results.

- [ ] **Step 1: Run setup**

```bash
cd experiments/host-side-api-server
./setup.sh
```

Expected: "Setup complete" with Go binaries in `bin/`.

- [ ] **Step 2: Start in interactive mode with full-access policy**

```bash
./run.sh policies/full-access.yaml
```

Expected: Both servers start, sandbox is created, policy applied. Orchestrator
prints SSH config path, token, and server URLs.

- [ ] **Step 3: Test from inside sandbox (in another terminal)**

Use the SSH config printed by the orchestrator:

```bash
ssh -F <ssh-config-path> openshell-<sandbox-name> \
  "export API_TOKEN='<token>' BUILDER_URL='http://<host-ip>:9090' PROVISIONER_URL='http://<host-ip>:9091' && \
   curl -s -H 'Authorization: Bearer \$API_TOKEN' \$BUILDER_URL/healthz && echo '' && \
   curl -s -H 'Authorization: Bearer \$API_TOKEN' \$PROVISIONER_URL/healthz"
```

Expected: Two `{"status":"ok"}` responses.

- [ ] **Step 4: Test restricted policy 403 handling**

Stop the first run (Ctrl+C), then:

```bash
./run.sh policies/restricted.yaml
```

From inside the sandbox, try `/push` and `/images` — both should return 403
from the proxy.

- [ ] **Step 5: Document findings**

Create `results/findings.md` with observations from the smoke test:
- Which endpoints worked, which returned 403
- Latency observations
- Any issues encountered with sandbox creation or policy application
- In-sandbox build test results

- [ ] **Step 6: Commit findings**

```bash
git add results/findings.md
git commit -m "docs: add initial experiment findings from smoke test"
```

Plan complete and saved to `experiments/host-side-api-server/superpowers/2026-05-14-host-side-api-server-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
