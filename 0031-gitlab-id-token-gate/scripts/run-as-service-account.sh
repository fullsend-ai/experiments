#!/usr/bin/env bash
# Run the service account side as the bot, with its token. The script
# reads the token from a hidden prompt, so it does not go into shell
# history. It creates an inactive schedule that the service account owns,
# runs it (scenario 1), and starts a pipeline through the API (scenario 9,
# which also starts the job token child of scenario 10). It prints only
# IDs.
set -euo pipefail
: "${GITLAB_HOST:=gitlab.com}"
: "${GITLAB_PROJECT:?set GITLAB_PROJECT to group/project}"
P=$(printf '%s' "$GITLAB_PROJECT" | jq -sRr @uri)
API="https://${GITLAB_HOST}/api/v4/projects/${P}"
read -rsp "Service account token: " TOKEN; echo
H="PRIVATE-TOKEN: ${TOKEN}"

sch=$(curl -sf -H "$H" -X POST "$API/pipeline_schedules" \
  --data-urlencode "description=ID token gate service account schedule" \
  --data-urlencode "ref=main" --data-urlencode "cron=0 0 1 1 *" \
  --data-urlencode "active=false" | jq -r .id)
echo "Schedule $sch created, owned by the service account."
curl -sf -H "$H" -X POST "$API/pipeline_schedules/$sch/play" >/dev/null
echo "Schedule $sch started."
pid=$(curl -sf -H "$H" -X POST "$API/pipeline" --data-urlencode "ref=main" | jq -r .id)
echo "API pipeline $pid started."
echo "SA_SCHEDULE_ID=$sch"
