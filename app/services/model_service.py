from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.llm_model import LLMModel
from app.schemas.model import ModelOut


class ModelService:
    def __init__(self, db: Session):
        self._db = db

    def list_models(self, *, enabled_only: bool = False) -> list[ModelOut]:
        stmt = (
            select(LLMModel)
            .options(joinedload(LLMModel.provider))
            .order_by(LLMModel.name)
        )
        if enabled_only:
            stmt = stmt.where(LLMModel.is_active.is_(True))

        models = self._db.scalars(stmt).all()
        return [
            ModelOut(
                id=str(model.id),
                name=model.name,
                display_name=model.display_name,
                provider=model.provider.provider_type.value,
                context_window=model.context_window,
                max_output_tokens=model.max_output_tokens,
                enabled=model.is_active,
            )
            for model in models
        ]
