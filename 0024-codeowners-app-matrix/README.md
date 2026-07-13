---
title: "24. CODEOWNERS + GitHub App approval matrix"
status: Active
topics:
  - github-apps
  - security
  - branch-protection
---

# 24. CODEOWNERS + GitHub App approval matrix

Date: 2026-07-13

Related: [ADR 0062 — Auto-merge](https://github.com/fullsend-ai/fullsend/pull/2791),
[CODEOWNERS blank-owner PR](https://github.com/fullsend-ai/fullsend/pull/2790)

## Hypotheses

| ID | Statement | Result |
|----|-----------|--------|
| H1 | A GitHub App with `contents: read` can submit an APPROVE review, but it does NOT count toward the "require approvals" branch protection rule. | |
| H2 | A GitHub App with `contents: write` can submit an APPROVE review, and it DOES count toward "require approvals". | |
| H3 | A blank-owner CODEOWNERS entry removes the code-owner review requirement for PRs that only touch that file. | |
| H4 | A PR touching both a blank-owner file and an owned file still requires code-owner approval for the owned file. | |
| H5 | When H2 and H3 are both true, a `contents: write` app is the sole approver on a blank-owner-only PR, and the PR is mergeable. | |
| H6 | When a PR touches both blank-owner and owned files, even a `contents: write` app cannot satisfy the code-owner requirement for the owned files. | |

## Approach

### Test infrastructure

- **Org:** `appdumpster`
- **Repo:** `appdumpster/codeowners-lab`
- **Team:** `@appdumpster/owners` (with the human operator as a member)
- **Apps:**
  - `appdumpster-read-bot` — `contents: read`, `pull_requests: write`
  - `appdumpster-write-bot` — `contents: write`, `pull_requests: write`

### Repo layout

```
CODEOWNERS:
  * @appdumpster/owners
  go.mod
  go.sum

Files: main.go, go.mod, go.sum
```

### Branch protection on `main`

- Require 1 approval
- Require review from code owners
- No status checks (keep it simple)

### Test matrix

| PR | Branch | Files touched | Approved by | Tests |
|----|--------|--------------|-------------|-------|
| 1 | `test/read-owned` | `main.go` | read-bot | H1 |
| 2 | `test/write-owned` | `main.go` | write-bot | H2, H4 partial |
| 3 | `test/read-blank` | `go.mod` | read-bot | H1, H3 |
| 4 | `test/write-blank` | `go.mod` | write-bot | H2, H3, H5 |
| 5 | `test/read-mixed` | `go.mod` + `main.go` | read-bot | H1, H4 |
| 6 | `test/write-mixed` | `go.mod` + `main.go` | write-bot | H2, H4, H6 |

### Measurement

For each PR, after the bot approves, query:
- `GET /repos/{owner}/{repo}/pulls/{number}/reviews` — confirm the review exists
- `GET /repos/{owner}/{repo}/pulls/{number}/merge` — can it merge? (405 = no, 204 = yes)
- `PUT /repos/{owner}/{repo}/pulls/{number}/merge` — attempt the merge, record status code and error message

## Results

_To be filled in after running `run_matrix.py`._

## Conclusion

_To be filled in after analyzing results._
