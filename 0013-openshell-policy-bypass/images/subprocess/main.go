package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
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
	fmt.Fprintf(os.Stdout, "safe-push-subprocess: called with args=%v\n", args)

	if isForce(args) {
		fmt.Fprintln(os.Stderr, "ERROR: safe-push: force push is not allowed")
		os.Exit(1)
	}

	gitArgs := []string{
		"-c", `credential.helper=!f() { echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f`,
		"push",
	}
	gitArgs = append(gitArgs, args...)
	cmd := exec.Command("git", gitArgs...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	cmd.Env = append(os.Environ(), "GIT_SSL_NO_VERIFY=1", "GIT_TERMINAL_PROMPT=0")

	if err := cmd.Run(); err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			os.Exit(exitErr.ExitCode())
		}
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}
}
