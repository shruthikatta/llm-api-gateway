from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config.store import get_config_store
from app.core.config import settings

logger = logging.getLogger(__name__)


class SlackAlertService:
    """Send operational alerts to a Slack incoming webhook."""

    def __init__(self) -> None:
        self._config = get_config_store().get().alerting

    @property
    def enabled(self) -> bool:
        webhook = settings.slack_webhook_url
        return self._config.enabled and webhook is not None and bool(webhook.get_secret_value())

    def send(self, *, title: str, text: str, fields: dict[str, Any] | None = None) -> bool:
        if not self.enabled:
            logger.debug("Slack alerting disabled; skipping alert title=%s", title)
            return False

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ]
        if fields:
            field_blocks = [
                {"type": "mrkdwn", "text": f"*{key}:*\n{value}"}
                for key, value in fields.items()
            ]
            blocks.append({"type": "section", "fields": field_blocks})

        payload = {"blocks": blocks}
        webhook_url = settings.slack_webhook_url.get_secret_value()  # type: ignore[union-attr]

        try:
            response = httpx.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("Failed to send Slack alert title=%s", title)
            return False

    def budget_warning(
        self,
        *,
        team_slug: str,
        period: str,
        spent_usd: float,
        budget_usd: float,
        threshold_pct: int,
    ) -> bool:
        if not self._config.budget_warnings:
            return False
        return self.send(
            title="Budget warning",
            text=(
                f"Team `{team_slug}` has reached the budget warning threshold "
                f"for the {period} period."
            ),
            fields={
                "Spent": f"${spent_usd:.4f}",
                "Budget": f"${budget_usd:.2f}",
                "Threshold": f"{threshold_pct}%",
            },
        )

    def circuit_open(self, *, provider: str, state: str) -> bool:
        if not self._config.circuit_open_alerts:
            return False
        return self.send(
            title="Circuit breaker opened",
            text=f"Provider `{provider}` circuit is now `{state}`.",
            fields={"Provider": provider, "State": state},
        )

    def high_error_rate(self, *, provider: str, error_rate: float) -> bool:
        threshold = self._config.error_rate_threshold
        if error_rate < threshold:
            return False
        return self.send(
            title="High provider error rate",
            text=(
                f"Provider `{provider}` error rate `{error_rate:.1%}` "
                f"exceeds threshold `{threshold:.1%}`."
            ),
            fields={"Provider": provider, "Error rate": f"{error_rate:.1%}"},
        )

    def test_alert(self) -> bool:
        return self.send(
            title="LLM API Gateway test alert",
            text="This is a test alert from the LLM API Gateway admin dashboard.",
            fields={"Status": "ok"},
        )
