import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from course.infrastructure.database import Base


class CourseModel(Base):
    """Shape of the ``courses`` table. No business rules: ``CourseRepository`` maps it to
    ``Course``. Lists (photos, syllabus, inclusions, refund tiers) are stored as JSON."""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_academy_id_start_date", "academy_id", "start_date"),
        Index("ix_courses_status_start_date", "status", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    academy_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academies.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    photos: Mapped[list[str]] = mapped_column(JSON)
    syllabus: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    included: Mapped[list[str]] = mapped_column(JSON)
    excluded: Mapped[list[str]] = mapped_column(JSON)
    venue_address: Mapped[str] = mapped_column(String(300))
    class_time: Mapped[time] = mapped_column(Time)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_currency: Mapped[str] = mapped_column(String(3))
    capacity: Mapped[int] = mapped_column(Integer)
    refund_tiers: Mapped[list[dict[str, int]]] = mapped_column(JSON)
    last_cancellation_days_before: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_modified_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancelled_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
