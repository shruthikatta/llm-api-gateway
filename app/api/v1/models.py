from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key, get_db
from app.models.api_key import APIKey
from app.schemas.model import ModelOut
from app.services.model_service import ModelService

router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[ModelOut])
def list_models(
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_current_api_key),
) -> list[ModelOut]:
    _ = api_key
    return ModelService(db).list_models()
