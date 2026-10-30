from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from course.domain.academy.academy import Academy


class AcademyDto(BaseModel):
    """What the application layer hands to the API. Plain values only, no domain objects."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    contact_email: str
    status: str
    rejection_reason: str | None
    is_verified: bool
    verified_at_utc: datetime | None
    created_at_utc: datetime
    last_modified_at_utc: datetime

    @classmethod
    def from_entity(cls, academy: Academy) -> AcademyDto:
        return cls(
            id=str(academy.id),
            name=academy.name.value,
            contact_email=academy.contact_email.value,
            status=academy.status.value,
            rejection_reason=academy.rejection_reason,
            is_verified=academy.is_verified,
            verified_at_utc=academy.verified_at,
            created_at_utc=academy.created_at_utc,
            last_modified_at_utc=academy.last_modified_at_utc,
        )
