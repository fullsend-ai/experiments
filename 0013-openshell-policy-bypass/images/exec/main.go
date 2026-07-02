package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
)

func isForce(args []string) bool {
	for _, a := range args {
		if a == "--force" || a == "-f" || a == "--force-with-lease" {
			return true
		}
		if strings.HasPrefix(a, "+") && strings.Contains(a, ":") {
			return true
		}
	}
	return false
}

func main() {
	args := os.Args[1:]
	fmt.Fprintf(os.Stdout, "safe-push-exec: called with args=%v\n", args)

	if isForce(args) {
		fmt.Fprintln(os.Stderr, "ERROR: safe-push: force push is not allowed")
		os.Exit(1)
	}

	git, err := exec.LookPath("git")
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: git not found on PATH")
		os.Exit(1)
	}

	env := append(os.Environ(), "GIT_SSL_NO_VERIFY=1")
	syscall.Exec(git, append([]string{"git", "push"}, args...), env)
}
