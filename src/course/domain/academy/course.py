from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import ClassVar

from course.common.entity import Entity
from course.common.errors.domain_error import DomainError, IDomainError
from course.common.identity import Id
from course.common.local_time import local_today
from course.common.result import Result, failure, success
from course.domain.academy.academy import Academy
from course.domain.academy.enums import CourseStatus
from course.domain.academy.errors import CourseErrorCodes
from course.domain.academy.value_objects._text import normalize_text
from course.domain.academy.value_objects.cancellation_policy import CancellationPolicy, RefundTier
from course.domain.academy.value_objects.date_range import DateRange
from course.domain.academy.value_objects.inclusions import Inclusions
from course.domain.academy.value_objects.money import Money
from course.domain.academy.value_objects.photo_gallery import PhotoGallery
from course.domain.academy.value_objects.syllabus import Syllabus, SyllabusItem
from course.domain.academy.value_objects.venue import Venue


class Course(Entity["Course"]):
    """A course listing: one group (cohort) with fixed start and end dates. It belongs to one academy,
    referenced by ``academy_id`` — the ``Academy`` is a separate entity, never held here. Contact details
    and the academy's other courses are resolved through that id by the application layer.

    The academy drives the whole lifecycle itself; there is no moderation (see ``CourseStatus``).
    The academy also sets the cancellation policy; enrollments snapshot it when they are made."""

    TITLE_MAXIMUM_LENGTH: ClassVar[int] = 200
    DESCRIPTION_MAXIMUM_LENGTH: ClassVar[int] = 5000
    CATEGORY_MAXIMUM_LENGTH: ClassVar[int] = 100
    CAPACITY_MINIMUM: ClassVar[int] = 1
    CAPACITY_MAXIMUM: ClassVar[int] = 10_000

    def __init__(
        self,
        course_id: Id[Course],
        academy_id: Id[Academy],
        title: str,
        description: str,
        gallery: PhotoGallery,
        syllabus: Syllabus,
        inclusions: Inclusions,
        venue: Venue,
        dates: DateRange,

        price_per_student: Money,
        capacity: int,
        status: CourseStatus,
        created_at: datetime,
        last_modified_at: datetime,
        archived_at: datetime | None = None,
        *,
        category: str,
        cancellation_policy: CancellationPolicy,
        cancelled_at: datetime | None = None,
    ) -> None:
        super().__init__(course_id, created_at, last_modified_at)
        self._academy_id = academy_id
        self._title = title
        self._description = description
        self._gallery = gallery
        self._syllabus = syllabus
        self._inclusions = inclusions
        self._venue = venue
        self._dates = dates
        self._price_per_student = price_per_student
        self._capacity = capacity
        self._status = status
        self._archived_at = archived_at
        self._category = category
        self._cancellation_policy = cancellation_policy
        self._cancelled_at = cancelled_at

    # ---- factories -------------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        academy_id: Id[Academy],
        title: str | None,
        description: str | None,
        category: str | None,
        photos: list[str],
        syllabus: list[SyllabusItem],
        included: list[str],
        excluded: list[str],
        venue_address: str | None,
        class_time: time,
        start_date: date,
        end_date: date,
        price_amount: Decimal,
        currency: str | None,
        capacity: int,
        refund_tiers: Sequence[RefundTier],
        last_cancellation_days_before: int,
        now: datetime,
    ) -> Result[Course, IDomainError]:
        """A new course starts as a draft; the academy publishes it when ready."""
        title_result = cls._validate_title(title)
        if title_result.is_failure:
            return failure(title_result.error)

        description_result = cls._validate_description(description)
        if description_result.is_failure:
            return failure(description_result.error)

        category_result = cls._validate_category(category)
        if category_result.is_failure:
            return failure(category_result.error)

        gallery_result = PhotoGallery.create(photos)
        if gallery_result.is_failure:
            return failure(gallery_result.error)

        syllabus_result = Syllabus.create(syllabus)
        if syllabus_result.is_failure:
            return failure(syllabus_result.error)

        inclusions_result = Inclusions.create(included, excluded)
        if inclusions_result.is_failure:
            return failure(inclusions_result.error)

        venue_result = Venue.create(venue_address, class_time)
        if venue_result.is_failure:
            return failure(venue_result.error)

        price_result = Money.create(price_amount, currency)
        if price_result.is_failure:
            return failure(price_result.error)

        capacity_result = cls._validate_capacity(capacity)
        if capacity_result.is_failure:
            return failure(capacity_result.error)

        policy_result = CancellationPolicy.create(refund_tiers, last_cancellation_days_before)
        if policy_result.is_failure:
            return failure(policy_result.error)

        dates_result = cls._validate_dates(start_date, end_date, now)
        if dates_result.is_failure:
            return failure(dates_result.error)

        return success(
            cls(
                Id.new(),
                academy_id,
                title_result.value,
                description_result.value,
                gallery_result.value,
                syllabus_result.value,
                inclusions_result.value,
                venue_result.value,
                dates_result.value,
                price_result.value,
                capacity_result.value,
                CourseStatus.DRAFT,
                now,
                now,
                category=category_result.value,
                cancellation_policy=policy_result.value,
            )
        )

    @classmethod
    def rehydrate(
        cls,
        *,
        course_id: uuid.UUID,
        academy_id: uuid.UUID,
        title: str,
        description: str,
        category: str,
        photos: list[str],
        syllabus: list[SyllabusItem],
        included: list[str],
        excluded: list[str],
        venue_address: str,
        class_time: time,
        start_date: date,
        end_date: date,
        price_amount: Decimal,
        currency: str,
        capacity: int,
        refund_tiers: Sequence[RefundTier],
        last_cancellation_days_before: int,
        status: str,
        created_at: datetime,
        last_modified_at: datetime,
        archived_at: datetime | None,
        cancelled_at: datetime | None,
    ) -> Course:
        """Rebuild a course loaded from storage. Business rules are not re-run (an old course
        may start in the past); ``CancellationPolicy`` still rejects corrupted data."""
        return cls(
            Id(course_id),
            Id(academy_id),
            title,
            description,
            PhotoGallery(tuple(photos)),
            Syllabus(tuple(sorted(syllabus, key=lambda i: i.order))),
            Inclusions(tuple(included), tuple(excluded)),
            Venue(venue_address, class_time),
            DateRange(start_date, end_date),
            Money(price_amount, currency),
            capacity,
            CourseStatus(status),
            created_at,
            last_modified_at,
            archived_at,
            category=category,
            cancellation_policy=CancellationPolicy(
                tuple(sorted(refund_tiers, key=lambda t: t.days_before, reverse=True)),
                last_cancellation_days_before,
            ),
            cancelled_at=cancelled_at,
        )

    # ---- properties ------------------------------------------------------------------------

    @property
    def academy_id(self) -> Id[Academy]:
        return self._academy_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> str:
        return self._category

    @property
    def gallery(self) -> PhotoGallery:
        return self._gallery

    @property
    def syllabus(self) -> Syllabus:
        return self._syllabus

    @property
    def inclusions(self) -> Inclusions:
        return self._inclusions

    @property
    def venue(self) -> Venue:
        return self._venue

    @property
    def dates(self) -> DateRange:
        return self._dates

    @property
    def start_date(self) -> date:
        return self._dates.start

    @property
    def end_date(self) -> date:
        return self._dates.end

    @property
    def price_per_student(self) -> Money:
        return self._price_per_student

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def cancellation_policy(self) -> CancellationPolicy:
        return self._cancellation_policy

    @property
    def status(self) -> CourseStatus:
        return self._status

    @property
    def archived_at(self) -> datetime | None:
        return self._archived_at

    @property
    def cancelled_at(self) -> datetime | None:
        return self._cancelled_at

    @property
    def is_published(self) -> bool:
        return self._status is CourseStatus.PUBLISHED

    @property
    def is_active(self) -> bool:
        """A live course: published or temporarily paused."""
        return self._status in (CourseStatus.PUBLISHED, CourseStatus.PAUSED)

    def is_enrollable(self, now: datetime) -> bool:
        """Students can enroll: published and not started yet (local date)."""
        return self.is_published and self._dates.start > local_today(now)

    # ---- behaviour -------------------------------------------------------------------------

    def publish(self, now: datetime) -> Result[None, IDomainError]:
        if self._status is not CourseStatus.DRAFT:
            return failure(self._transition_error("publish"))
        started = self._ensure_starts_in_future(now)
        if started.is_failure:
            return started
        return self._move_to(CourseStatus.PUBLISHED, now)

    def pause(self, now: datetime) -> Result[None, IDomainError]:
        """Hide from search; existing enrollments stay valid."""
        if self._status is not CourseStatus.PUBLISHED:
            return failure(self._transition_error("pause"))
        return self._move_to(CourseStatus.PAUSED, now)

    def resume(self, now: datetime) -> Result[None, IDomainError]:
        if self._status is not CourseStatus.PAUSED:
            return failure(self._transition_error("resume"))
        started = self._ensure_starts_in_future(now)
        if started.is_failure:
            return started
        return self._move_to(CourseStatus.PUBLISHED, now)

    def cancel(self, now: datetime) -> Result[None, IDomainError]:
        """The academy cancels the course; every student is refunded in full (handled by enrollments)."""
        if not self.is_active:
            return failure(self._transition_error("cancel"))
        self._cancelled_at = now
        return self._move_to(CourseStatus.CANCELLED, now)

    def archive(self, active_enrollment_count: int, now: datetime) -> Result[None, IDomainError]:
        """Replaces deletion: old enrollments keep pointing at the course."""
        if self._status is CourseStatus.ARCHIVED:
            return failure(
                DomainError.conflict("Course is already archived.", code=CourseErrorCodes.ALREADY_ARCHIVED)
            )
        if active_enrollment_count > 0:
            return failure(
                DomainError.conflict(
                    "A course with active enrollments cannot be archived. Cancel it first.",
                    code=CourseErrorCodes.HAS_ACTIVE_ENROLLMENTS,
                )
            )
        self._archived_at = now
        return self._move_to(CourseStatus.ARCHIVED, now)

    def duplicate(self, start_date: date, end_date: date, now: datetime) -> Result[Course, IDomainError]:
        """A new draft with every field copied, including the cancellation policy, for new dates."""
        dates_result = self._validate_dates(start_date, end_date, now)
        if dates_result.is_failure:
            return failure(dates_result.error)
        return success(
            Course(
                Id.new(),
                self._academy_id,
                self._title,
                self._description,
                self._gallery,
                self._syllabus,
                self._inclusions,
                self._venue,
                dates_result.value,
                self._price_per_student,
                self._capacity,
                CourseStatus.DRAFT,
                now,
                now,
                category=self._category,
                cancellation_policy=self._cancellation_policy,
            )
        )

    # ---- helpers ---------------------------------------------------------------------------

    def _move_to(self, status: CourseStatus, now: datetime) -> Result[None, IDomainError]:
        self._status = status
        self._last_modified_at_utc = now
        return success(None)

    def _ensure_starts_in_future(self, now: datetime) -> Result[None, IDomainError]:
        if self._dates.start <= local_today(now):
            return failure(
                DomainError.validation("The course has already started.", code=CourseErrorCodes.START_IN_PAST)
            )
        return success(None)

    def _transition_error(self, action: str) -> IDomainError:
        return DomainError.conflict(
            f"Cannot {action} a course that is {self._status.value}.",
            code=CourseErrorCodes.INVALID_TRANSITION,
        )

    @classmethod
    def _validate_dates(cls, start_date: date, end_date: date, now: datetime) -> Result[DateRange, IDomainError]:
        dates_result = DateRange.create(start_date, end_date)
        if dates_result.is_failure:
            return failure(dates_result.error)
        # cross-field rule no single value object can own: a new course must start in the future
        if dates_result.value.start <= local_today(now):
            return failure(
                DomainError.validation(
                    "A new course must start in the future.",
                    code=CourseErrorCodes.START_IN_PAST,
                )
            )
        return success(dates_result.value)

    @classmethod
    def _validate_title(cls, title: str | None) -> Result[str, IDomainError]:
        normalized = normalize_text(title or "")
        if not normalized:
            return failure(DomainError.validation("Title is required.", code=CourseErrorCodes.TITLE_EMPTY))
        if len(normalized) > cls.TITLE_MAXIMUM_LENGTH:
            return failure(
                DomainError.validation(
                    f"Title cannot exceed {cls.TITLE_MAXIMUM_LENGTH} characters.",
                    code=CourseErrorCodes.TITLE_TOO_LONG,
                )
            )
        return success(normalized)

    @classmethod
    def _validate_description(cls, description: str | None) -> Result[str, IDomainError]:
        stripped = (description or "").strip()
        if not stripped:
            return failure(
                DomainError.validation("Description is required.", code=CourseErrorCodes.DESCRIPTION_TOO_SHORT)
            )
        if len(stripped) > cls.DESCRIPTION_MAXIMUM_LENGTH:
            return failure(
                DomainError.validation(
                    f"Description cannot exceed {cls.DESCRIPTION_MAXIMUM_LENGTH} characters.",
                    code=CourseErrorCodes.DESCRIPTION_TOO_LONG,
                )
            )
        return success(stripped)

    @classmethod
    def _validate_category(cls, category: str | None) -> Result[str, IDomainError]:
        normalized = normalize_text(category or "")
        if not normalized:
            return failure(
                DomainError.validation("Category is required.", code=CourseErrorCodes.CATEGORY_EMPTY)
            )
        if len(normalized) > cls.CATEGORY_MAXIMUM_LENGTH:
            return failure(
                DomainError.validation(
                    f"Category cannot exceed {cls.CATEGORY_MAXIMUM_LENGTH} characters.",
                    code=CourseErrorCodes.CATEGORY_TOO_LONG,
                )
            )
        return success(normalized)

    @classmethod
    def _validate_capacity(cls, capacity: int) -> Result[int, IDomainError]:
        if isinstance(capacity, bool) or not cls.CAPACITY_MINIMUM <= capacity <= cls.CAPACITY_MAXIMUM:
            return failure(
                DomainError.validation(
                    f"Capacity must be between {cls.CAPACITY_MINIMUM} and {cls.CAPACITY_MAXIMUM} seats.",
                    code=CourseErrorCodes.CAPACITY_INVALID,
                )
            )
        return success(capacity)
