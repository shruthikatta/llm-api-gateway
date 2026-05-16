from __future__ import annotations

from pydantic import BaseModel


class ModelOut(BaseModel):
    id: str
    name: str
    display_name: str
    provider: str
    context_window: int
    max_output_tokens: int
    enabled: bool
