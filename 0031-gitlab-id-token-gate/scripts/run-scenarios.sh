#!/usr/bin/env bash
# Run the attack scenarios as the glab user (the "person"), and print the
# gate result of each. Set SA_SCHEDULE_ID to the service account's
# schedule ID, after the service account has run it once, to also run the
# scenarios against its pipeline. Uses only false credentials.
set -euo pipefail
. "$(dirname "$0")/common.sh"
P="$GITLAB_PROJECT_ENC"
TMP=$(mktemp -d)

wait_pipeline() {  # $1 pipeline id
  local s
  for _ in $(seq 1 60); do
    s=$(glab api "projects/$P/pipelines/$1" | jq -r .status)
    case "$s" in created|pending|running|preparing|waiting_for_resource) sleep 10 ;; *) return ;; esac
  done
}
wait_job() {  # $1 job id
  local s
  for _ in $(seq 1 60); do
    s=$(glab api "projects/$P/jobs/$1" | jq -r .status)
    case "$s" in created|pending|running|preparing|waiting_for_resource) sleep 10 ;; *) return ;; esac
  done
}
gate_lines() {  # $1 job id
  glab api "projects/$P/jobs/$1/trace" | sed -E 's/^[^ ]+ [^ ]+ //' \
    | grep -E "CLAIMS|GATE RESULT|INJECTED|^\{\"id\"" | grep -v '^\$' || true
}
show_pipeline() {  # $1 label, $2 pipeline id
  wait_pipeline "$2"
  echo "=== $1 (pipeline $2, source $(glab api "projects/$P/pipelines/$2" | jq -r .source))"
  glab api "projects/$P/pipelines/$2/jobs" | jq -r '.[] | select(.status != "manual") | "\(.id) \(.name)"' |
    while read -r j n; do echo "--- $n"; gate_lines "$j"; done
}
start() {  # $1 label, $2 JSON body
  printf '%s' "$2" > "$TMP/body.json"
  local id child
  id=$(glab api -X POST "projects/$P/pipeline" -H 'Content-Type: application/json' --input "$TMP/body.json" | jq -r .id)
  show_pipeline "$1" "$id"
  child=$(glab api "projects/$P/pipelines?source=pipeline&order_by=id&sort=desc&per_page=1" | jq -r '.[0].id // empty')
  if [ -n "$child" ] && [ "$child" -gt "$id" ]; then show_pipeline "$1, job token child" "$child"; fi
}

old=$(glab api "projects/$P" | jq -r .ci_pipeline_variables_minimum_override_role)
if [ "$old" = developer ]; then
  trap 'rm -rf "$TMP"' EXIT
  echo "Variable role is already developer."
else
  trap 'glab api -X PUT "projects/$P" -f ci_pipeline_variables_minimum_override_role="$old" >/dev/null; rm -rf "$TMP"' EXIT
  glab api -X PUT "projects/$P" -f ci_pipeline_variables_minimum_override_role=developer >/dev/null
  echo "Variable role set to developer for the run (restored to $old on exit)."
fi

start "Plain API pipeline" '{"ref":"main"}'
start "Forged CI_PIPELINE_SOURCE=schedule" '{"ref":"main","variables":[{"key":"CI_PIPELINE_SOURCE","value":"schedule"}]}'
cat > "$TMP/bashenv.json" <<'JSON'
{"ref":"main","variables":[
 {"key":"BASH_ENV","variable_type":"file","raw":true,"value":"echo \"INJECTED: id_token_len=${#GATE_ID_TOKEN}\" >&2\n"}
]}
JSON
start "BASH_ENV injection" "$(cat "$TMP/bashenv.json")"

SCH="${SA_SCHEDULE_ID:-}"
[ -n "$SCH" ] || { echo "SA_SCHEDULE_ID not set: skipping the service account pipeline scenarios."; exit 0; }
last=$(glab api "projects/$P/pipeline_schedules/$SCH" | jq -r '.last_pipeline.id // empty')
[ -n "$last" ] || { echo "The service account schedule has not run yet."; exit 0; }

echo "=== Add a BASH_ENV variable to the service account schedule (not the owner)"
glab api -X POST "projects/$P/pipeline_schedules/$SCH/variables" -f key=BASH_ENV -f value='echo x' -f variable_type=file 2>&1 | head -c 120 || true; echo

jid=$(glab api "projects/$P/pipelines/$last/jobs" | jq -r '.[] | select(.name=="gate") | .id')
nj=$(glab api -X POST "projects/$P/jobs/$jid/retry" | jq -r .id)
wait_job "$nj"
echo "=== Retry of the service account gate job (job $nj)"; gate_lines "$nj"

mj=$(glab api "projects/$P/pipelines/$last/jobs" | jq -r '.[] | select(.name=="gate-manual" and .status=="manual") | .id')
if [ -n "$mj" ]; then
  printf '%s' '{"job_variables_attributes":[{"key":"BASH_ENV","value":"/dev/null"}]}' > "$TMP/play.json"
  glab api -X POST "projects/$P/jobs/$mj/play" -H 'Content-Type: application/json' --input "$TMP/play.json" >/dev/null
  wait_job "$mj"
  echo "=== Manual gate job in the service account pipeline, played with job variables (job $mj)"; gate_lines "$mj"
fi
