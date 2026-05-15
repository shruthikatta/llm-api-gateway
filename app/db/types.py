import uuid

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column


def uuid_primary_key():
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )