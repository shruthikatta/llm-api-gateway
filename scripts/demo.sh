#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${GATEWAY_URL:-http://localhost:8000}"
API_KEY="${GATEWAY_API_KEY:-}"

echo "== LLM API Gateway Demo =="
echo "Base URL: $BASE_URL"
echo

echo "1. Liveness"
curl -fsS "$BASE_URL/live" | python3 -m json.tool
echo

echo "2. Health"
curl -fsS "$BASE_URL/health" | python3 -m json.tool
echo

if [[ -z "$API_KEY" ]]; then
  echo "Set GATEWAY_API_KEY to run authenticated demo steps."
  echo "Generate one with: python -m app.db.seed"
  exit 0
fi

echo "3. Chat completion (mock)"
curl -fsS "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mock-chat",
    "messages": [{"role": "user", "content": "demo hello"}]
  }' | python3 -m json.tool
echo

echo "4. Streaming chat"
curl -Ns "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mock-chat",
    "stream": true,
    "messages": [{"role": "user", "content": "demo stream"}]
  }' | head -n 6
echo

echo "5. Admin analytics overview"
curl -fsS "$BASE_URL/v1/admin/analytics/overview?days=7" \
  -H "Authorization: Bearer $API_KEY" | python3 -m json.tool
echo

echo "6. Prometheus metrics sample"
curl -fsS "$BASE_URL/metrics" | head -n 15
echo
echo "Demo complete. Open $BASE_URL/dashboard for the admin console."
