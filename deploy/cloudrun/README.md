# Cloud Run deployment

## Prerequisites

- Google Cloud project with Cloud Run, Cloud Build, Secret Manager enabled
- PostgreSQL and Redis (Cloud SQL + Memorystore, or managed equivalents)
- Secrets in Secret Manager:
  - `ai-gateway-jwt-secret`
  - `openai-api-key`
  - `slack-webhook-url` (optional)

## Manual deploy

```bash
export GCP_PROJECT_ID=your-project
export GCP_REGION=us-central1
chmod +x deploy/cloudrun/deploy.sh
./deploy/cloudrun/deploy.sh
```

## CI/CD

GitHub Actions workflow `.github/workflows/deploy.yml` runs tests on every push and deploys to Cloud Run on `main` when GCP secrets are configured.

## Observability on GCP

| Signal | Integration |
|--------|-------------|
| Logs | JSON stdout → Cloud Logging (automatic on Cloud Run) |
| Metrics | Scrape `/metrics` via Google Managed Prometheus or Cloud Monitoring custom metrics |
| Traces | Set `telemetry.otlp_endpoint` to Cloud Trace OTLP collector |
| Dashboards | Import `observability/grafana/dashboards/ai-gateway-operations.json` or use Cloud Monitoring dashboards |

## Security notes

- Store all secrets in Secret Manager, never in `gateway.yaml`
- Restrict `/dashboard` and `/v1/admin/*` behind IAM or an identity-aware proxy in production
- Use least-privilege service accounts for Cloud Run
