#!/usr/bin/env bash
set -euo pipefail

REPO="${1:?Usage: setup-repo.sh <owner/repo>}"
BRANCH="experiment/policy-test"

echo "Setting up test branch '$BRANCH' on $REPO"

MAIN_SHA=$(gh api "repos/$REPO/git/ref/heads/main" -q .object.sha)
echo "  main SHA: $MAIN_SHA"

if gh api "repos/$REPO/git/ref/heads/$BRANCH" -q .object.sha >/dev/null 2>&1; then
    echo "  Branch '$BRANCH' already exists, resetting to main"
    gh api -X PATCH "repos/$REPO/git/refs/heads/$BRANCH" \
        -f sha="$MAIN_SHA" -F force=true -q .object.sha >/dev/null
else
    echo "  Creating branch '$BRANCH'"
    gh api "repos/$REPO/git/refs" \
        -f ref="refs/heads/$BRANCH" \
        -f sha="$MAIN_SHA" -q .ref >/dev/null
fi

TREE_SHA=$(gh api "repos/$REPO/git/commits/$MAIN_SHA" -q .tree.sha)

BLOB_SHA=$(gh api "repos/$REPO/git/blobs" \
    -f content="Setup commit for policy bypass experiment" \
    -f encoding=utf-8 \
    -q .sha)

NEW_TREE_SHA=$(gh api "repos/$REPO/git/trees" \
    -f "tree[][path]=EXPERIMENT_MARKER.txt" \
    -f "tree[][mode]=100644" \
    -f "tree[][type]=blob" \
    -f "tree[][sha]=$BLOB_SHA" \
    -f "base_tree=$TREE_SHA" \
    -q .sha)

COMMIT_SHA=$(gh api "repos/$REPO/git/commits" \
    -f message="experiment: setup marker commit for policy bypass test" \
    -f "tree=$NEW_TREE_SHA" \
    -f "parents[]=$MAIN_SHA" \
    -q .sha)

gh api -X PATCH "repos/$REPO/git/refs/heads/$BRANCH" \
    -f sha="$COMMIT_SHA" -q .object.sha >/dev/null

echo "  Branch '$BRANCH' ready at $COMMIT_SHA"
echo "$COMMIT_SHA" > /tmp/policy-test-setup-sha.txt
echo "  SHA saved to /tmp/policy-test-setup-sha.txt"
