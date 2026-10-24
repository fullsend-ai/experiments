#!/usr/bin/env bash
# One-command offline reproduction for experiment 0029.
#
# Setup (network, first run only): installs the pinned shared gemara-owner CLI
# into .cache/bin with `go install`. Everything after setup runs offline:
# synthetic fixtures, a fixed evaluation time, no credentials, no model calls,
# no forge writes. Set GEMARA_OWNER to use an already-built binary instead.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
revision="61a01465478e50d8e9b3e21dd056fdef90baff30"

if test -z "${GEMARA_OWNER:-}"; then
  export GEMARA_OWNER="${here}/.cache/bin/gemara-owner"
  if ! test -x "${GEMARA_OWNER}"; then
    echo "setup: installing github.com/ascerra/fullsend-gemara-integration/cmd/gemara-owner@${revision}" >&2
    GOBIN="${here}/.cache/bin" go install \
      "github.com/ascerra/fullsend-gemara-integration/cmd/gemara-owner@${revision}"
  fi
fi

cd "${here}"
python3 scripts/scenarios.py "$@"
python3 -m unittest discover -s tests -q
