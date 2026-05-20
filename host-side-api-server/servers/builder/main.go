package main

import (
	"bytes"
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
	"syscall"
	"time"

	"github.com/google/uuid"
)

var (
	bearerToken string
	sandboxName string
)

type BuildRequest struct {
	Tag         string `json:"tag"`
	Dockerfile  string `json:"dockerfile"`
	ContextDir  string `json:"context_dir"`
	Dest        string `json:"dest"`
	Sandbox     string `json:"sandbox"`
}

type BuildResponse struct {
	ID     string `json:"id"`
	Tag    string `json:"tag"`
	Status string `json:"status"`
	Output string `json:"output"`
	Error  string `json:"error,omitempty"`
}

type PushRequest struct {
	Tag string `json:"tag"`
}

type PushResponse struct {
	Tag    string `json:"tag"`
	Status string `json:"status"`
	Output string `json:"output"`
	Error  string `json:"error,omitempty"`
}

// authMiddleware validates bearer token
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			http.Error(w, `{"error":"missing authorization header"}`, http.StatusUnauthorized)
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			http.Error(w, `{"error":"invalid authorization format"}`, http.StatusUnauthorized)
			return
		}

		if parts[1] != bearerToken {
			http.Error(w, `{"error":"invalid token"}`, http.StatusUnauthorized)
			return
		}

		next(w, r)
	}
}

// detectContainerRuntime returns "podman" or "docker"
func detectContainerRuntime() string {
	if _, err := exec.LookPath("podman"); err == nil {
		return "podman"
	}
	return "docker"
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func jsonResponse(w http.ResponseWriter, resp interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func buildHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	var req BuildRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid JSON: %s"}`, err), http.StatusBadRequest)
		return
	}

	if req.Tag == "" {
		http.Error(w, `{"error":"tag is required"}`, http.StatusBadRequest)
		return
	}

	if req.Dockerfile == "" {
		req.Dockerfile = "Dockerfile"
	}
	if req.ContextDir == "" {
		req.ContextDir = "."
	}

	sb := req.Sandbox
	if sb == "" {
		sb = sandboxName
	}

	buildID := uuid.New().String()
	runtime := detectContainerRuntime()

	resp := BuildResponse{
		ID:  buildID,
		Tag: req.Tag,
	}

	// Download build context from sandbox
	if sb == "" {
		resp.Status = "failed"
		resp.Error = "sandbox name is required (pass 'sandbox' in request body)"
		jsonResponse(w, resp)
		return
	}

	tmpDir, err := os.MkdirTemp("", "build-ctx-")
	if err != nil {
		resp.Status = "failed"
		resp.Error = fmt.Sprintf("failed to create temp dir: %v", err)
		jsonResponse(w, resp)
		return
	}
	defer os.RemoveAll(tmpDir)

	localContext := tmpDir + "/context"
	log.Printf("Downloading build context from sandbox %s:%s", sb, req.ContextDir)
	dlCmd := exec.Command("openshell", "sandbox", "download", sb, req.ContextDir, localContext)
	if dlOut, err := dlCmd.CombinedOutput(); err != nil {
		resp.Status = "failed"
		resp.Error = fmt.Sprintf("failed to download context from sandbox: %v: %s", err, dlOut)
		jsonResponse(w, resp)
		return
	}

	// Build image from downloaded context
	dockerfilePath := localContext + "/" + req.Dockerfile
	log.Printf("Building image %s from %s", req.Tag, dockerfilePath)
	cmd := exec.Command(runtime, "build", "-t", req.Tag, "-f", dockerfilePath, localContext)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		resp.Status = "failed"
		resp.Error = err.Error()
		resp.Output = stdout.String() + stderr.String()
		jsonResponse(w, resp)
		return
	}

	resp.Status = "success"
	resp.Output = stdout.String() + stderr.String()

	// Upload image tarball back to sandbox
	if req.Dest != "" {
		tmpFile, err := os.CreateTemp("", "image-*.tar")
		if err != nil {
			resp.Error = fmt.Sprintf("failed to create temp file: %v", err)
			jsonResponse(w, resp)
			return
		}
		defer os.Remove(tmpFile.Name())
		tmpFile.Close()

		saveCmd := exec.Command(runtime, "save", "-o", tmpFile.Name(), req.Tag)
		if saveOut, err := saveCmd.CombinedOutput(); err != nil {
			resp.Status = "failed"
			resp.Error = fmt.Sprintf("image save failed: %v: %s", err, saveOut)
			jsonResponse(w, resp)
			return
		}

		log.Printf("Uploading image tarball to sandbox %s:%s", sb, req.Dest)
		uploadCmd := exec.Command("openshell", "sandbox", "upload", sb, tmpFile.Name(), req.Dest)
		if uploadOut, err := uploadCmd.CombinedOutput(); err != nil {
			resp.Status = "failed"
			resp.Error = fmt.Sprintf("upload to sandbox failed: %v: %s", err, uploadOut)
			jsonResponse(w, resp)
			return
		}
		resp.Output += fmt.Sprintf("\nImage uploaded to sandbox at %s", req.Dest)
	}

	jsonResponse(w, resp)
}

func pushHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	var req PushRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid JSON: %s"}`, err), http.StatusBadRequest)
		return
	}

	if req.Tag == "" {
		http.Error(w, `{"error":"tag is required"}`, http.StatusBadRequest)
		return
	}

	runtime := detectContainerRuntime()
	cmd := exec.Command(runtime, "push", req.Tag)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	resp := PushResponse{
		Tag:    req.Tag,
		Output: stdout.String() + stderr.String(),
	}

	if err != nil {
		resp.Status = "failed"
		resp.Error = err.Error()
	} else {
		resp.Status = "success"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

func imagesHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	runtime := detectContainerRuntime()
	cmd := exec.Command(runtime, "images", "--format", "json")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"%s","stderr":"%s"}`, err, stderr.String()), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(stdout.Bytes())
}

func openapiHandler(w http.ResponseWriter, r *http.Request) {
	spec := map[string]interface{}{
		"openapi": "3.0.0",
		"info": map[string]interface{}{
			"title":   "Container Builder API",
			"version": "1.0.0",
		},
		"paths": map[string]interface{}{
			"/healthz": map[string]interface{}{
				"get": map[string]interface{}{
					"summary": "Health check",
					"responses": map[string]interface{}{
						"200": map[string]interface{}{
							"description": "Service is healthy",
							"content": map[string]interface{}{
								"application/json": map[string]interface{}{
									"schema": map[string]interface{}{
										"type": "object",
										"properties": map[string]interface{}{
											"status": map[string]string{"type": "string"},
										},
									},
								},
							},
						},
					},
				},
			},
			"/build": map[string]interface{}{
				"post": map[string]interface{}{
					"summary": "Build a container image",
					"security": []map[string][]string{
						{"bearerAuth": []string{}},
					},
					"requestBody": map[string]interface{}{
						"required": true,
						"content": map[string]interface{}{
							"application/json": map[string]interface{}{
								"schema": map[string]interface{}{
									"type": "object",
									"required": []string{"tag"},
									"properties": map[string]interface{}{
										"tag":         map[string]string{"type": "string"},
										"dockerfile":  map[string]string{"type": "string", "default": "Dockerfile"},
										"context_dir": map[string]string{"type": "string", "description": "Path to the build context directory inside the sandbox", "default": "."},
										"dest":        map[string]string{"type": "string", "description": "Sandbox path to upload the built image tarball to"},
										"sandbox":     map[string]string{"type": "string", "description": "Sandbox name (use $(hostname | sed 's/^sandbox-//') from inside the sandbox)"},
									},
								},
							},
						},
					},
					"responses": map[string]interface{}{
						"200": map[string]interface{}{
							"description": "Build result",
							"content": map[string]interface{}{
								"application/json": map[string]interface{}{
									"schema": map[string]interface{}{
										"type": "object",
										"properties": map[string]interface{}{
											"id":     map[string]string{"type": "string"},
											"tag":    map[string]string{"type": "string"},
											"status": map[string]string{"type": "string"},
											"output": map[string]string{"type": "string"},
											"error":  map[string]string{"type": "string"},
										},
									},
								},
							},
						},
					},
				},
			},
			"/push": map[string]interface{}{
				"post": map[string]interface{}{
					"summary": "Push a container image",
					"security": []map[string][]string{
						{"bearerAuth": []string{}},
					},
					"requestBody": map[string]interface{}{
						"required": true,
						"content": map[string]interface{}{
							"application/json": map[string]interface{}{
								"schema": map[string]interface{}{
									"type": "object",
									"required": []string{"tag"},
									"properties": map[string]interface{}{
										"tag": map[string]string{"type": "string"},
									},
								},
							},
						},
					},
					"responses": map[string]interface{}{
						"200": map[string]interface{}{
							"description": "Push result",
							"content": map[string]interface{}{
								"application/json": map[string]interface{}{
									"schema": map[string]interface{}{
										"type": "object",
										"properties": map[string]interface{}{
											"tag":    map[string]string{"type": "string"},
											"status": map[string]string{"type": "string"},
											"output": map[string]string{"type": "string"},
											"error":  map[string]string{"type": "string"},
										},
									},
								},
							},
						},
					},
				},
			},
			"/images": map[string]interface{}{
				"get": map[string]interface{}{
					"summary": "List container images",
					"security": []map[string][]string{
						{"bearerAuth": []string{}},
					},
					"responses": map[string]interface{}{
						"200": map[string]interface{}{
							"description": "List of images in JSON format",
							"content": map[string]interface{}{
								"application/json": map[string]interface{}{
									"schema": map[string]interface{}{
										"type": "array",
									},
								},
							},
						},
					},
				},
			},
		},
		"components": map[string]interface{}{
			"securitySchemes": map[string]interface{}{
				"bearerAuth": map[string]string{
					"type":   "http",
					"scheme": "bearer",
				},
			},
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(spec)
}

func toolsHandler(w http.ResponseWriter, r *http.Request) {
	tools := []map[string]interface{}{
		{
			"name":        "build_container",
			"description": "Build a container image using podman or docker",
			"endpoint":    "/build",
			"method":      "POST",
			"input_schema": map[string]interface{}{
				"type": "object",
				"required": []string{"tag"},
				"properties": map[string]interface{}{
					"tag": map[string]interface{}{
						"type":        "string",
						"description": "Tag for the container image",
					},
					"dockerfile": map[string]interface{}{
						"type":        "string",
						"description": "Path to Dockerfile (default: Dockerfile)",
						"default":     "Dockerfile",
					},
					"context_dir": map[string]interface{}{
						"type":        "string",
						"description": "Path to the build context directory inside the sandbox",
						"default":     ".",
					},
					"sandbox": map[string]interface{}{
						"type":        "string",
						"description": "Sandbox name. Use $(hostname) from inside the sandbox.",
					},
					"dest": map[string]interface{}{
						"type":        "string",
						"description": "Sandbox path to upload the built image tarball to. If omitted, the image stays on the host only.",
					},
				},
			},
		},
		{
			"name":        "push_container",
			"description": "Push a container image to a registry",
			"endpoint":    "/push",
			"method":      "POST",
			"input_schema": map[string]interface{}{
				"type": "object",
				"required": []string{"tag"},
				"properties": map[string]interface{}{
					"tag": map[string]interface{}{
						"type":        "string",
						"description": "Tag of the container image to push",
					},
				},
			},
		},
		{
			"name":        "list_images",
			"description": "List all container images",
			"endpoint":    "/images",
			"method":      "GET",
			"input_schema": map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			},
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tools)
}

func main() {
	port := flag.Int("port", 9090, "Port to listen on")
	token := flag.String("token", "", "Bearer token for authentication (required)")
	sandbox := flag.String("sandbox", "", "OpenShell sandbox name for uploading build artifacts")
	flag.Parse()

	if *token == "" {
		log.Fatal("--token is required")
	}

	bearerToken = *token
	sandboxName = *sandbox

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", healthHandler)
	mux.HandleFunc("/build", authMiddleware(buildHandler))
	mux.HandleFunc("/push", authMiddleware(pushHandler))
	mux.HandleFunc("/images", authMiddleware(imagesHandler))
	mux.HandleFunc("/openapi.json", openapiHandler)
	mux.HandleFunc("/tools.json", toolsHandler)

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", *port),
		Handler: mux,
	}

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		log.Printf("Starting builder server on port %d", *port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-stop
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server shutdown error: %v", err)
	}

	log.Println("Server stopped")
}
