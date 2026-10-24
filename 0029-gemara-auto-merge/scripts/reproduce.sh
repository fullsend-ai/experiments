#!/usr/bin/env bash
# One-command offline reproduction for experiment 0029.
#
# Setup (network, first run only): installs the pinned shared gemara-owner CLI
# into .cache/bin with `go install`. Everything after setup runs offline:
# synthetic fixtures, a fixed evaluation time, no credentials, no model calls,
# no forge writes. Set GEMARA_OWNER to use an already-built binary instead.
# Either binary must embed the pinned module revision (`go version -m`); a
# cached binary at another revision is reinstalled, a GEMARA_OWNER one fails.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
module="github.com/ascerra/fullsend-gemara-integration"
revision="61a01465478e50d8e9b3e21dd056fdef90baff30"

is_pinned() {
  local version
  version="$(go version -m "$1" 2>/dev/null | awk -v m="${module}" '$1 == "mod" && $2 == m {print $3}')"
  case "${version}" in
    *-"${revision:0:12}") return 0 ;;
    *) return 1 ;;
  esac
}

if test -z "${GEMARA_OWNER:-}"; then
  export GEMARA_OWNER="${here}/.cache/bin/gemara-owner"
  if ! test -x "${GEMARA_OWNER}" || ! is_pinned "${GEMARA_OWNER}"; then
    echo "setup: installing ${module}/cmd/gemara-owner@${revision}" >&2
    rm -f "${GEMARA_OWNER}"
    GOBIN="${here}/.cache/bin" go install "${module}/cmd/gemara-owner@${revision}"
  fi
else
  # Resolve against the caller's directory before the cd below.
  case "${GEMARA_OWNER}" in
    /*) ;;
    *) export GEMARA_OWNER="${PWD}/${GEMARA_OWNER}" ;;
  esac
fi

if ! is_pinned "${GEMARA_OWNER}"; then
  echo "error: ${GEMARA_OWNER} does not embed ${module} at ${revision} (go version -m)" >&2
  exit 1
fi

cd "${here}"
python3 scripts/scenarios.py "$@"
python3 -m unittest discover -s tests -q
