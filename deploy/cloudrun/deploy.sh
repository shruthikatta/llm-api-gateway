#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ai-gateway}"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "Building ${IMAGE}"
gcloud builds submit --tag "${IMAGE}"

echo "Deploying to Cloud Run"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets=JWT_SECRET=ai-gateway-jwt-secret:latest,OPENAI_API_KEY=openai-api-key:latest,SLACK_WEBHOOK_URL=slack-webhook-url:latest

echo "Deployed. Fetch URL:"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.url)'
