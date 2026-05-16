from __future__ import annotations

from pydantic import BaseModel


class ProviderOut(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    enabled: bool
