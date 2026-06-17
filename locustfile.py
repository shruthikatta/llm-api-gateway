"""
Locust load test for the LLM API Gateway.

Usage:
  pip install -r requirements-dev.txt
  export GATEWAY_API_KEY=<seeded-key>
  locust -f locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task


class GatewayUser(HttpUser):
    wait_time = between(0.01, 0.1)
    api_key = os.environ.get("GATEWAY_API_KEY", "")

    def on_start(self) -> None:
        if not self.api_key:
            raise RuntimeError("Set GATEWAY_API_KEY before running Locust.")

    @task(8)
    def chat_completion(self) -> None:
        self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "mock-chat",
                "messages": [{"role": "user", "content": "locust load test"}],
            },
            name="/v1/chat/completions",
        )

    @task(2)
    def streaming_chat(self) -> None:
        with self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "mock-chat",
                "stream": True,
                "messages": [{"role": "user", "content": "stream load test"}],
            },
            stream=True,
            name="/v1/chat/completions [stream]",
        ) as response:
            if response.status_code == 200:
                for _ in response.iter_lines():
                    pass

    @task(1)
    def health_check(self) -> None:
        self.client.get("/health", name="/health")
