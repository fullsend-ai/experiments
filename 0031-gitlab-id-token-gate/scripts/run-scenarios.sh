#!/usr/bin/env bash
# Run the attack scenarios as the glab user (the "person"), and print
# the gate result of each. The service account scenario needs SA_LOGIN to
# run its own schedule (see README). Uses only false credentials.
set -euo pipefail
. "$(dirname "$0")/common.sh"
P="$GITLAB_PROJECT_ENC"
TMP=$(mktemp -d)

wait_job() {  # $1 pipeline id -> prints gate lines
  local id=$1 s j
  for _ in $(seq 1 60); do
    s=$(glab api "projects/$P/pipelines/$id" | jq -r .status)
    case "$s" in created|pending|running|preparing|waiting_for_resource) sleep 10 ;; *) break ;; esac
  done
  j=$(glab api "projects/$P/pipelines/$id/jobs" | jq -r '.[0].id')
  glab api "projects/$P/jobs/$j/trace" | sed -E 's/^[^ ]+ [^ ]+ //' | grep -E "CLAIMS|GATE RESULT|INJECTED" | grep -v '^\$' || true
}
run() {  # $1 label, $2 JSON body
  printf '%s' "$2" > "$TMP/body.json"
  local id
  id=$(glab api -X POST "projects/$P/pipeline" -H 'Content-Type: application/json' --input "$TMP/body.json" | jq -r .id)
  echo "=== $1 (pipeline $id)"; wait_job "$id"
}

old=$(glab api "projects/$P" | jq -r .ci_pipeline_variables_minimum_override_role)
trap 'glab api -X PUT "projects/$P" -f ci_pipeline_variables_minimum_override_role="$old" >/dev/null; rm -rf "$TMP"' EXIT
glab api -X PUT "projects/$P" -f ci_pipeline_variables_minimum_override_role=developer >/dev/null
echo "Variable role set to developer for the run (restored to $old on exit)."

run "Plain API pipeline" '{"ref":"main","variables":[{"key":"GATE_RUN","value":"1"}]}'
run "Forged CI_PIPELINE_SOURCE=schedule" '{"ref":"main","variables":[{"key":"GATE_RUN","value":"1"},{"key":"CI_PIPELINE_SOURCE","value":"schedule"}]}'
cat > "$TMP/body.json" <<'JSON'
{"ref":"main","variables":[
 {"key":"GATE_RUN","value":"1"},
 {"key":"BASH_ENV","variable_type":"file","raw":true,"value":"echo \"INJECTED: id_token_len=${#GATE_ID_TOKEN}\" >&2\n"}
]}
JSON
id=$(glab api -X POST "projects/$P/pipeline" -H 'Content-Type: application/json' --input "$TMP/body.json" | jq -r .id)
echo "=== BASH_ENV injection (pipeline $id)"; wait_job "$id"

SCH="${SA_SCHEDULE_ID:-}"
if [ -n "$SCH" ]; then
  echo "=== Edit the service account schedule as a non-owner"
  glab api -X POST "projects/$P/pipeline_schedules/$SCH/variables" -f key=BASH_ENV -f value='echo x' -f variable_type=file 2>&1 | head -c 120; echo
  last=$(glab api "projects/$P/pipeline_schedules/$SCH" | jq -r '.last_pipeline.id // empty')
  if [ -n "$last" ]; then
    jid=$(glab api "projects/$P/pipelines/$last/jobs" | jq -r '.[0].id')
    nj=$(glab api -X POST "projects/$P/jobs/$jid/retry" | jq -r .id)
    for _ in $(seq 1 60); do s=$(glab api "projects/$P/jobs/$nj" | jq -r .status); case "$s" in created|pending|running) sleep 10 ;; *) break ;; esac; done
    echo "=== Retry of the service account job (job $nj)"
    glab api "projects/$P/jobs/$nj/trace" | sed -E 's/^[^ ]+ [^ ]+ //' | grep -E "CLAIMS|GATE RESULT" || true
  fi
fi
