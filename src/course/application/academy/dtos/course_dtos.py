from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from course.domain.academy.course import Course


class SyllabusItemDto(BaseModel):
    model_config = ConfigDict(frozen=True)

    order: int
    title: str
    detail: str = ""


class RefundTierDto(BaseModel):
    """``days_before`` or more days before the course, the student gets ``refund_percent`` back."""

    model_config = ConfigDict(frozen=True)

    days_before: int
    refund_percent: int


class CreateCourseCommand(BaseModel):
    """Input for a new course. Fields are loose on purpose: the domain validates them."""

    title: str | None = None
    description: str | None = None
    category: str | None = None
    photos: list[str] = Field(default_factory=list)
    syllabus: list[SyllabusItemDto] = Field(default_factory=list)
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    venue_address: str | None = None
    class_time: time
    start_date: date
    end_date: date
    price_amount: Decimal
    currency: str = "AZN"
    capacity: int
    refund_tiers: list[RefundTierDto] = Field(default_factory=list)
    last_cancellation_days_before: int


class DuplicateCourseCommand(BaseModel):
    start_date: date
    end_date: date


class CourseDto(BaseModel):
    """What the application layer hands to the API. Plain values only, no domain objects."""

    model_config = ConfigDict(frozen=True)

    id: str
    academy_id: str
    title: str
    description: str
    category: str
    photos: list[str]
    cover_photo: str
    syllabus: list[SyllabusItemDto]
    included: list[str]
    excluded: list[str]
    venue_address: str
    class_time: time
    start_date: date
    end_date: date
    duration_days: int
    price_amount: Decimal
    currency: str
    capacity: int
    refund_tiers: list[RefundTierDto]
    last_cancellation_days_before: int
    status: str
    created_at_utc: datetime
    last_modified_at_utc: datetime
    cancelled_at_utc: datetime | None
    archived_at_utc: datetime | None

    @classmethod
    def from_entity(cls, course: Course) -> CourseDto:
        policy = course.cancellation_policy
        return cls(
            id=str(course.id),
            academy_id=str(course.academy_id),
            title=course.title,
            description=course.description,
            category=course.category,
            photos=list(course.gallery.photos),
            cover_photo=course.gallery.cover,
            syllabus=[
                SyllabusItemDto(order=item.order, title=item.title, detail=item.detail)
                for item in course.syllabus.items
            ],
            included=list(course.inclusions.included),
            excluded=list(course.inclusions.excluded),
            venue_address=course.venue.address,
            class_time=course.venue.class_time,
            start_date=course.start_date,
            end_date=course.end_date,
            duration_days=course.dates.duration_days,
            price_amount=course.price_per_student.amount,
            currency=course.price_per_student.currency,
            capacity=course.capacity,
            refund_tiers=[
                RefundTierDto(days_before=tier.days_before, refund_percent=tier.refund_percent)
                for tier in policy.tiers
            ],
            last_cancellation_days_before=policy.last_cancellation_days_before,
            status=course.status.value,
            created_at_utc=course.created_at_utc,
            last_modified_at_utc=course.last_modified_at_utc,
            cancelled_at_utc=course.cancelled_at,
            archived_at_utc=course.archived_at,
        )
