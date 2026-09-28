#!/usr/bin/env bash
# Build the image with Cloud Build and deploy it to Cloud Run.
#
# Usage, from the repo root:
#   deploy/cloudrun.sh
#
# Requires billing on the project and the ga4-agent-runtime service account (BigQuery Job User only).
# The Anthropic key is stored once in Secret Manager and read by Cloud Run at startup:
#   gcloud services enable secretmanager.googleapis.com
#   (set -a; . ./.env; printf %s "$ANTHROPIC_API_KEY" | gcloud secrets create anthropic-api-key --data-file=-)
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"  # the dataset lives in the US multi-region
SERVICE="${SERVICE:-ga4-analyst}"
MODEL="${ANTHROPIC_MODEL:-claude-sonnet-5}"
RUNTIME_SA="ga4-agent-runtime@${PROJECT}.iam.gserviceaccount.com"
BUILD_SA="ga4-agent-builder@${PROJECT}.iam.gserviceaccount.com"
SECRET="anthropic-api-key"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com --project "$PROJECT"

if ! gcloud secrets versions describe latest --secret "$SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "Secret $SECRET is missing or has no value. Create it first (see the header of this script)." >&2
  exit 1
fi
gcloud secrets add-iam-policy-binding "$SECRET" --project "$PROJECT" \
  --member "serviceAccount:$RUNTIME_SA" --role roles/secretmanager.secretAccessor >/dev/null

# Builds run as their own account with only the Cloud Run builder role, not as the project's default account.
if ! gcloud iam service-accounts describe "$BUILD_SA" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create ga4-agent-builder --project "$PROJECT" --display-name "GA4 agent image builds"
fi
gcloud projects add-iam-policy-binding "$PROJECT" --condition None \
  --member "serviceAccount:$BUILD_SA" --role roles/run.builder >/dev/null

# TODO(security-hardening): Set a custom BigQuery "Query usage per day" quota on the project
# WHY: the project has billing, so BigQuery has no daily cap; the per-query byte limit does not bound how many queries run in a day
# DONE-WHEN: gcloud alpha services quota list --service=bigquery.googleapis.com --consumer=projects/$PROJECT shows a consumer override of at most 1 TiB for QueryUsagePerDay

# TODO(security-hardening): Add a billing budget with an email alert
# WHY: a forgotten public link should be noticed long before it costs real money
# DONE-WHEN: gcloud billing budgets list --billing-account=<account> shows a $5 budget with thresholds at 50% and 100%

# TODO(security-hardening): Set a monthly spend limit on the Anthropic key's workspace and leave auto-reload off
# WHY: the key is the most expensive thing behind the public link; the app's own limits do not cap a month
# DONE-WHEN: the Anthropic console Limits page shows a monthly spend limit for the workspace and auto-reload is disabled

# TODO(security-hardening): Put an access code in front of the public link before sharing it beyond the reviewers
# WHY: --allow-unauthenticated lets anyone with the URL spend credits
# DONE-WHEN: POST /api/conversations without the code returns 401 and the page asks for the code before showing the chat

# Scale to zero when idle (conversations live in memory, so they are lost after the instance stops).
# One instance at most, so a burst of traffic cannot multiply cost; the timeout covers a long answer.
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --build-service-account "projects/${PROJECT}/serviceAccounts/${BUILD_SA}" \
  --service-account "$RUNTIME_SA" \
  --set-secrets "ANTHROPIC_API_KEY=${SECRET}:latest" \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT},ANTHROPIC_MODEL=${MODEL}" \
  --min-instances 0 \
  --max-instances 1 \
  --timeout 300 \
  --memory 1Gi \
  --allow-unauthenticated
