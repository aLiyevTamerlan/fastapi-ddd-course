import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from course.infrastructure.database import Base


class AcademyRow(Base):
    """Shape of the ``academies`` table. No business rules: ``AcademyRepository`` maps it to ``Academy``."""

    __tablename__ = "academies"
    __table_args__ = (
        Index("ix_academies_status_created_at_utc", "status", "created_at_utc"),
        Index("uq_academies_contact_email", "contact_email", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(32))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=false())
    verified_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_modified_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# Names are unique case-insensitively, the same way AcademyRepository.exists_with_name compares them.
# The service checks first and gives a clear 409; this index is the last guard against two concurrent requests.
Index("uq_academies_name_lower", func.lower(AcademyRow.name), unique=True)
