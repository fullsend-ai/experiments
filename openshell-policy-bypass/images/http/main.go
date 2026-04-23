package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/go-git/go-git/v5"
	"github.com/go-git/go-git/v5/config"
	"github.com/go-git/go-git/v5/plumbing/transport/http"
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
	fmt.Fprintf(os.Stdout, "safe-push-http: called with args=%v\n", args)

	if isForce(args) {
		fmt.Fprintln(os.Stderr, "ERROR: safe-push: force push is not allowed")
		os.Exit(1)
	}

	repo, err := git.PlainOpen(".")
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: failed to open repo: %v\n", err)
		os.Exit(1)
	}

	remote := "origin"
	if len(args) > 0 {
		remote = args[0]
	}

	refspec := "refs/heads/*:refs/heads/*"
	if len(args) > 1 {
		branch := args[1]
		if !strings.Contains(branch, ":") {
			refspec = fmt.Sprintf("refs/heads/%s:refs/heads/%s", branch, branch)
		} else {
			refspec = branch
		}
	}

	opts := &git.PushOptions{
		RemoteName: remote,
		RefSpecs:   []config.RefSpec{config.RefSpec(refspec)},
	}
	if token := os.Getenv("GITHUB_TOKEN"); token != "" {
		opts.Auth = &http.BasicAuth{Username: "x-access-token", Password: token}
	}
	err = repo.Push(opts)
	if err != nil {
		if err == git.NoErrAlreadyUpToDate {
			fmt.Println("Everything up-to-date")
			return
		}
		fmt.Fprintf(os.Stderr, "ERROR: push failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Push successful")
}
