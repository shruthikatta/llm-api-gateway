from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key, get_db
from app.models.api_key import APIKey
from app.schemas.provider import ProviderOut
from app.services.provider_service import ProviderService

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
) -> list[ProviderOut]:
    _ = api_key
    return ProviderService(db).list_providers()
