from __future__ import annotations

import re
from typing import Any

from app.exceptions.gateway import ContentFilterError
from app.schemas.chat import ChatCompletionRequest


def apply_input_content_filter(
    request: ChatCompletionRequest,
    filter_config: dict[str, Any],
) -> None:
    """
    Validate inbound prompts against team content filter rules.

    Config shape (all optional):
      {
        "max_input_chars": 100000,
        "blocked_terms": ["secret-project"],
        "blocked_patterns": ["(?i)ssn\\\\s*\\\\d{3}"]
      }
    """
    if not filter_config:
        return

    joined = "\n".join(message.content for message in request.messages)
    max_chars = filter_config.get("max_input_chars")
    if isinstance(max_chars, int) and max_chars > 0 and len(joined) > max_chars:
        raise ContentFilterError(
            "Input exceeds maximum allowed length.",
            details={"max_input_chars": max_chars, "actual_chars": len(joined)},
        )

    lowered = joined.lower()
    for term in filter_config.get("blocked_terms") or []:
        if str(term).lower() in lowered:
            raise ContentFilterError(
                "Input blocked by content filter.",
                details={"matched": "blocked_term"},
            )

    for pattern in filter_config.get("blocked_patterns") or []:
        try:
            if re.search(str(pattern), joined, flags=re.IGNORECASE | re.MULTILINE):
                raise ContentFilterError(
                    "Input blocked by content filter.",
                    details={"matched": "blocked_pattern"},
                )
        except re.error as exc:
            raise ContentFilterError(
                "Invalid content filter pattern configuration.",
                details={"pattern": pattern, "error": str(exc)},
            ) from exc


def apply_output_content_filter(
    text: str,
    filter_config: dict[str, Any],
) -> str:
    """
    Redact or block outbound assistant text.

    If block_output_on_match is true, raise; otherwise redact matched terms.
    """
    if not filter_config or not text:
        return text

    blocked_terms = [str(t) for t in (filter_config.get("blocked_terms") or [])]
    block_on_match = bool(filter_config.get("block_output_on_match", False))

    result = text
    for term in blocked_terms:
        if term.lower() in result.lower():
            if block_on_match:
                raise ContentFilterError(
                    "Output blocked by content filter.",
                    details={"matched": "blocked_term"},
                )
            result = re.sub(re.escape(term), "[REDACTED]", result, flags=re.IGNORECASE)

    for pattern in filter_config.get("blocked_patterns") or []:
        try:
            if re.search(str(pattern), result, flags=re.IGNORECASE | re.MULTILINE):
                if block_on_match:
                    raise ContentFilterError(
                        "Output blocked by content filter.",
                        details={"matched": "blocked_pattern"},
                    )
                result = re.sub(
                    str(pattern),
                    "[REDACTED]",
                    result,
                    flags=re.IGNORECASE | re.MULTILINE,
                )
        except re.error as exc:
            raise ContentFilterError(
                "Invalid content filter pattern configuration.",
                details={"pattern": pattern, "error": str(exc)},
            ) from exc

    return result
