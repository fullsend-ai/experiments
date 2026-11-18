#!/usr/bin/env bash
# Create the WIF pool, the GitLab OIDC provider with the gate condition,
# and a fake forge credential that only the pool can read.
set -euo pipefail
. "$(dirname "$0")/common.sh"

COND="assertion.project_path == '${GITLAB_PROJECT}' \
&& assertion.ref == 'main' \
&& assertion.ref_protected == 'true' \
&& assertion.ci_config_ref_uri == '${GITLAB_HOST}/${GITLAB_PROJECT}//.gitlab-ci.yml@refs/heads/main' \
&& assertion.pipeline_source in ['schedule', 'pipeline', 'api'] \
&& assertion.user_login == '${SA_LOGIN}'"

JWK=()
[ -z "$JWKS_FILE" ] || JWK=(--jwk-json-path "$JWKS_FILE")

gcloud services enable secretmanager.googleapis.com sts.googleapis.com iam.googleapis.com --project "$GCP_PROJECT"
gcloud iam workload-identity-pools create "$POOL" --project "$GCP_PROJECT" --location global \
  --display-name "ID token gate experiment" --description "Experiment 0031. Delete with teardown.sh."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project "$GCP_PROJECT" \
  --location global --workload-identity-pool "$POOL" --issuer-uri "https://${GITLAB_HOST}" ${JWK[@]+"${JWK[@]}"} \
  --allowed-audiences "$WIF_AUDIENCE" \
  --attribute-mapping "google.subject=assertion.sub,attribute.user_login=assertion.user_login,attribute.pipeline_source=assertion.pipeline_source,attribute.project_path=assertion.project_path" \
  --attribute-condition "$COND"
printf '%s' "FAKE-$(openssl rand -hex 12)" | gcloud secrets create "$SECRET" --project "$GCP_PROJECT" \
  --replication-policy automatic --data-file=- --labels purpose=experiment-0031
gcloud secrets add-iam-policy-binding "$SECRET" --project "$GCP_PROJECT" \
  --role roles/secretmanager.secretAccessor \
  --member "principalSet://iam.googleapis.com/projects/${GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/*" >/dev/null
echo "Gate condition: $COND"
