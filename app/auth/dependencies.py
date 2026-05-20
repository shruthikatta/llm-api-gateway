from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator

from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidAPIKey, MissingAPIKey
from app.auth.security import hash_api_key
from app.db.session import SessionLocal
from app.exceptions.gateway import TeamDisabledError
from app.models.api_key import APIKey
from app.models.user import User
from app.repositories.api_key_repository import APIKeyRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def extract_api_key(
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    if x_api_key:
        return x_api_key
    raise MissingAPIKey()


def get_current_api_key(
    raw_key: str = Depends(extract_api_key),
    db: Session = Depends(get_db),
) -> APIKey:
    repository = APIKeyRepository(db)
    api_key = repository.get_by_hash_with_user(hash_api_key(raw_key))

    # Collapse all authn failures into one client-facing error.
    if api_key is None:
        raise InvalidAPIKey()

    if not api_key.is_active:
        raise InvalidAPIKey()

    if api_key.expires_at is not None and _as_utc(api_key.expires_at) < datetime.now(
        timezone.utc
    ):
        raise InvalidAPIKey()

    user = api_key.user
    if not user.is_active:
        raise InvalidAPIKey()

    if not user.organization.is_active:
        raise InvalidAPIKey()

    if api_key.team_id is None or api_key.team is None:
        raise TeamDisabledError()

    if not api_key.team.is_active:
        raise TeamDisabledError()

    repository.touch_last_used(api_key)
    return api_key


def get_current_user(
    api_key: APIKey = Depends(get_current_api_key),
) -> User:
    return api_key.user
