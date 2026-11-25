# Shared settings. All values come from the environment, with no
# defaults for project identifiers.
: "${GCP_PROJECT:?set GCP_PROJECT to the GCP project ID}"
: "${GITLAB_PROJECT:?set GITLAB_PROJECT to group/project}"
# GITLAB_HOST also selects the instance for glab. JWKS_FILE, if set, is
# uploaded to WIF in place of OIDC discovery, for an instance that Google
# cannot reach.
GITLAB_HOST="${GITLAB_HOST:-gitlab.com}"
JWKS_FILE="${JWKS_FILE:-}"
: "${SA_LOGIN:?set SA_LOGIN to the GitLab username that plays the service account}"
POOL="${POOL:-id-token-gate}"
PROVIDER="${PROVIDER:-gitlab-com}"
SECRET="${SECRET:-id-token-gate-fake-forge-credential}"
GCP_PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT" --format='value(projectNumber)')
WIF_AUDIENCE="//iam.googleapis.com/projects/${GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
SECRET_URL="https://secretmanager.googleapis.com/v1/projects/${GCP_PROJECT}/secrets/${SECRET}/versions/latest:access"
GITLAB_PROJECT_ENC=$(printf '%s' "$GITLAB_PROJECT" | jq -sRr @uri)
export GITLAB_HOST JWKS_FILE GCP_PROJECT GITLAB_PROJECT SA_LOGIN POOL PROVIDER SECRET GCP_PROJECT_NUMBER WIF_AUDIENCE SECRET_URL GITLAB_PROJECT_ENC
