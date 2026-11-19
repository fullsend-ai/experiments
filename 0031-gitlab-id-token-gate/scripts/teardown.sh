#!/usr/bin/env bash
# Remove the GCP parts. Delete the GitLab project, or its schedules and
# CI files, by hand.
set -euo pipefail
. "$(dirname "$0")/common.sh"
gcloud secrets delete "$SECRET" --project "$GCP_PROJECT" --quiet
gcloud iam workload-identity-pools providers delete "$PROVIDER" --project "$GCP_PROJECT" --location global --workload-identity-pool "$POOL" --quiet
gcloud iam workload-identity-pools delete "$POOL" --project "$GCP_PROJECT" --location global --quiet
echo "Deleted. A deleted pool stays soft-deleted for 30 days and blocks reuse of its name."
