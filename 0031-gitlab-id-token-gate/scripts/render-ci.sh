#!/usr/bin/env bash
# Write .gitlab-ci.yml and gate.sh into a checkout of the GitLab project,
# with the endpoints as literals.
set -euo pipefail
. "$(dirname "$0")/common.sh"
DEST="${1:?usage: render-ci.sh <path to a checkout of the GitLab project>}"
HERE="$(cd "$(dirname "$0")/../gitlab" && pwd)"
envsubst '${WIF_AUDIENCE}' < "$HERE/gitlab-ci.yml.tmpl" > "$DEST/.gitlab-ci.yml"
envsubst '${WIF_AUDIENCE} ${SECRET_URL}' < "$HERE/gate.sh.tmpl" > "$DEST/gate.sh"
echo "Wrote $DEST/.gitlab-ci.yml and $DEST/gate.sh. Commit and push them to main."
