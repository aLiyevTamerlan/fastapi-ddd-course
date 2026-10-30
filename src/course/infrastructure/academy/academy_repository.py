from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from course.application.academy.abstractions.academy_repository import IAcademyRepository
from course.common.identity import Id
from course.domain.academy.academy import Academy
from course.domain.academy.enums import AcademyStatus
from course.infrastructure.academy.academy_row import AcademyRow


class AcademyRepository(IAcademyRepository):
    """The only place that writes academies to the database. Commits after each successful write."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, academy: Academy) -> None:
        self._session.add(AcademyRow(**_to_values(academy)))
        await self._session.commit()

    async def update(self, academy: Academy) -> None:
        values = _to_values(academy)
        academy_id = values.pop("id")
        await self._session.execute(update(AcademyRow).where(AcademyRow.id == academy_id).values(**values))
        await self._session.commit()

    async def get(self, academy_id: Id[Academy]) -> Academy | None:
        row = await self._session.get(AcademyRow, academy_id.value)
        return _to_entity(row) if row is not None else None

    async def list_by_status(self, status: AcademyStatus | None) -> list[Academy]:
        query = select(AcademyRow).order_by(AcademyRow.created_at_utc)
        if status is not None:
            query = query.where(AcademyRow.status == status.value)
        rows = (await self._session.scalars(query)).all()
        return [_to_entity(row) for row in rows]

    async def exists_with_name(self, name: str, excluding: Id[Academy] | None = None) -> bool:
        query = select(AcademyRow.id).where(func.lower(AcademyRow.name) == name.lower())
        if excluding is not None:
            query = query.where(AcademyRow.id != excluding.value)
        return (await self._session.scalar(query.limit(1))) is not None

    async def exists_with_contact_email(self, contact_email: str, excluding: Id[Academy] | None = None) -> bool:
        query = select(AcademyRow.id).where(AcademyRow.contact_email == contact_email)
        if excluding is not None:
            query = query.where(AcademyRow.id != excluding.value)
        return (await self._session.scalar(query.limit(1))) is not None


def _to_values(academy: Academy) -> dict[str, Any]:
    return {
        "id": academy.id.value,
        "name": academy.name.value,
        "contact_email": academy.contact_email.value,
        "status": academy.status.value,
        "rejection_reason": academy.rejection_reason,
        "is_verified": academy.is_verified,
        "verified_at_utc": academy.verified_at,
        "created_at_utc": academy.created_at_utc,
        "last_modified_at_utc": academy.last_modified_at_utc,
    }


def _to_entity(row: AcademyRow) -> Academy:
    # Always rehydrate, never call the constructor: storage data is trusted, not re-validated.
    return Academy.rehydrate(
        academy_id=row.id,
        name=row.name,
        contact_email=row.contact_email,
        status=row.status,
        rejection_reason=row.rejection_reason,
        created_at=_as_utc(row.created_at_utc),
        last_modified_at=_as_utc(row.last_modified_at_utc),
        is_verified=row.is_verified,
        verified_at=_as_utc(row.verified_at_utc) if row.verified_at_utc is not None else None,
    )


def _as_utc(value: datetime) -> datetime:
    """Postgres ``timestamptz`` returns aware values; drivers without time zones (SQLite) return naive UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
