from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from course.application.academy.abstractions.course_repository import ICourseRepository
from course.common.identity import Id
from course.domain.academy.academy import Academy
from course.domain.academy.course import Course
from course.domain.academy.enums import CourseStatus
from course.domain.academy.value_objects.cancellation_policy import RefundTier
from course.domain.academy.value_objects.syllabus import SyllabusItem
from course.infrastructure.academy.course_model import CourseModel


class CourseRepository(ICourseRepository):
    """The only place that writes courses to the database. Commits after each successful write."""

    _ACTIVE_STATUSES = (CourseStatus.PUBLISHED.value, CourseStatus.PAUSED.value)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, course: Course) -> None:
        self._session.add(CourseModel(**self._to_values(course)))
        await self._session.commit()

    async def update(self, course: Course) -> None:
        values = self._to_values(course)
        course_id = values.pop("id")
        await self._session.execute(
            update(CourseModel).where(CourseModel.id == course_id).values(**values)
        )
        await self._session.commit()

    async def get(self, course_id: Id[Course]) -> Course | None:
        model = await self._session.get(CourseModel, course_id.value)
        return self._to_entity(model) if model is not None else None

    async def list_by_academy(self, academy_id: Id[Academy]) -> list[Course]:
        query = (
            select(CourseModel)
            .where(CourseModel.academy_id == academy_id.value)
            .where(CourseModel.status != CourseStatus.ARCHIVED.value)
            .order_by(CourseModel.start_date)
        )
        return [self._to_entity(model) for model in (await self._session.scalars(query)).all()]

    async def list_active_by_academy(self, academy_id: Id[Academy]) -> list[Course]:
        query = (
            select(CourseModel)
            .where(CourseModel.academy_id == academy_id.value)
            .where(CourseModel.status.in_(self._ACTIVE_STATUSES))
        )
        return [self._to_entity(model) for model in (await self._session.scalars(query)).all()]

    async def list_published(self, starting_after: date) -> list[Course]:
        query = (
            select(CourseModel)
            .where(CourseModel.status == CourseStatus.PUBLISHED.value)
            .where(CourseModel.start_date > starting_after)
            .order_by(CourseModel.start_date)
        )
        return [self._to_entity(model) for model in (await self._session.scalars(query)).all()]

    # ---- mapping ---------------------------------------------------------------------------

    @classmethod
    def _to_values(cls, course: Course) -> dict[str, Any]:
        policy = course.cancellation_policy
        return {
            "id": course.id.value,
            "academy_id": course.academy_id.value,
            "title": course.title,
            "description": course.description,
            "category": course.category,
            "photos": list(course.gallery.photos),
            "syllabus": [
                {"order": item.order, "title": item.title, "detail": item.detail}
                for item in course.syllabus.items
            ],
            "included": list(course.inclusions.included),
            "excluded": list(course.inclusions.excluded),
            "venue_address": course.venue.address,
            "class_time": course.venue.class_time,
            "start_date": course.start_date,
            "end_date": course.end_date,
            "price_amount": course.price_per_student.amount,
            "price_currency": course.price_per_student.currency,
            "capacity": course.capacity,
            "refund_tiers": [
                {"days_before": tier.days_before, "refund_percent": tier.refund_percent} for tier in policy.tiers
            ],
            "last_cancellation_days_before": policy.last_cancellation_days_before,
            "status": course.status.value,
            "created_at_utc": course.created_at_utc,
            "last_modified_at_utc": course.last_modified_at_utc,
            "cancelled_at_utc": course.cancelled_at,
            "archived_at_utc": course.archived_at,
        }

    @classmethod
    def _to_entity(cls, model: CourseModel) -> Course:
        # Always rehydrate, never call create(): stored data is trusted, not re-validated.
        return Course.rehydrate(
            course_id=model.id,
            academy_id=model.academy_id,
            title=model.title,
            description=model.description,
            category=model.category,
            photos=list(model.photos),
            syllabus=[SyllabusItem(item["order"], item["title"], item["detail"]) for item in model.syllabus],
            included=list(model.included),
            excluded=list(model.excluded),
            venue_address=model.venue_address,
            class_time=model.class_time,
            start_date=model.start_date,
            end_date=model.end_date,
            price_amount=model.price_amount,
            currency=model.price_currency,
            capacity=model.capacity,
            refund_tiers=[RefundTier(tier["days_before"], tier["refund_percent"]) for tier in model.refund_tiers],
            last_cancellation_days_before=model.last_cancellation_days_before,
            status=model.status,
            created_at=cls._as_utc(model.created_at_utc),
            last_modified_at=cls._as_utc(model.last_modified_at_utc),
            archived_at=cls._as_utc(model.archived_at_utc) if model.archived_at_utc is not None else None,
            cancelled_at=cls._as_utc(model.cancelled_at_utc) if model.cancelled_at_utc is not None else None,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Postgres ``timestamptz`` returns aware values; drivers without time zones (SQLite) return naive UTC."""
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
