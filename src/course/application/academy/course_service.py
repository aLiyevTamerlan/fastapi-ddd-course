from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from course.application.academy.abstractions.academy_repository import IAcademyRepository
from course.application.academy.abstractions.course_repository import ICourseRepository
from course.application.academy.dtos.course_dtos import (
    CourseDto,
    CreateCourseCommand,
    DuplicateCourseCommand,
)
from course.common.errors.domain_error import DomainError, IDomainError
from course.common.identity import Id
from course.common.local_time import local_today
from course.common.result import Result, failure, success
from course.common.time_provider import TimeProvider
from course.domain.academy.academy import Academy
from course.domain.academy.course import Course
from course.domain.academy.errors import AcademyErrorCodes, CourseErrorCodes
from course.domain.academy.value_objects.cancellation_policy import RefundTier
from course.domain.academy.value_objects.syllabus import SyllabusItem
from course.domain.course.services.course_overlap_policy import CourseOverlapPolicy


class CourseService:
    """Use cases for courses: load, let the domain decide, save. No business rules live here."""

    def __init__(
        self,
        academies: IAcademyRepository,
        courses: ICourseRepository,
        time_provider: TimeProvider,
        overlap_policy: CourseOverlapPolicy | None = None,
    ) -> None:
        self._academies = academies
        self._courses = courses
        self._time = time_provider
        self._overlap_policy = overlap_policy or CourseOverlapPolicy()

    # ---- academy dashboard ------------------------------------------------------------------

    async def create(
        self, academy_id: Id[Academy], command: CreateCourseCommand
    ) -> Result[CourseDto, IDomainError]:
        academy = await self._load_academy(academy_id)
        if academy.is_failure:
            return failure(academy.error)
        can_publish = academy.value.ensure_can_publish()
        if can_publish.is_failure:
            return failure(can_publish.error)

        created = Course.create(
            academy_id=academy_id,
            title=command.title,
            description=command.description,
            category=command.category,
            photos=command.photos,
            syllabus=[SyllabusItem(item.order, item.title, item.detail) for item in command.syllabus],
            included=command.included,
            excluded=command.excluded,
            venue_address=command.venue_address,
            class_time=command.class_time,
            start_date=command.start_date,
            end_date=command.end_date,
            price_amount=command.price_amount,
            currency=command.currency,
            capacity=command.capacity,
            refund_tiers=[RefundTier(tier.days_before, tier.refund_percent) for tier in command.refund_tiers],
            last_cancellation_days_before=command.last_cancellation_days_before,
            now=self._time.now(),
        )
        if created.is_failure:
            return failure(created.error)
        await self._courses.add(created.value)
        return success(CourseDto.from_entity(created.value))

    async def get(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        loaded = await self._load_owned(academy_id, course_id)
        if loaded.is_failure:
            return failure(loaded.error)
        return success(CourseDto.from_entity(loaded.value))

    async def list_for_academy(self, academy_id: Id[Academy]) -> Result[list[CourseDto], IDomainError]:
        academy = await self._load_academy(academy_id)
        if academy.is_failure:
            return failure(academy.error)
        courses = await self._courses.list_by_academy(academy_id)
        return success([CourseDto.from_entity(a) for a in courses])

    async def publish(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        return await self._go_live(academy_id, course_id, lambda a, now: a.publish(now))

    async def resume(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        return await self._go_live(academy_id, course_id, lambda a, now: a.resume(now))

    async def pause(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        return await self._change(academy_id, course_id, lambda a, now: a.pause(now))

    async def cancel(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        # Refunding the students is the enrollment module's job once it exists.
        return await self._change(academy_id, course_id, lambda a, now: a.cancel(now))

    async def archive(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[CourseDto, IDomainError]:
        # Enrollments do not exist yet, so there are never active ones; the enrollment module
        # will supply the real count.
        return await self._change(academy_id, course_id, lambda a, now: a.archive(0, now))


    # ---- public (students) ----------------------------------------------------------------

    async def list_published(self) -> Result[list[CourseDto], IDomainError]:
        today = local_today(self._time.now())
        courses = await self._courses.list_published(starting_after=today)
        return success([CourseDto.from_entity(a) for a in courses])

    async def get_published(self, course_id: Id[Course]) -> Result[CourseDto, IDomainError]:
        course = await self._courses.get(course_id)
        if course is None or not course.is_published:
            return failure(_course_not_found())
        return success(CourseDto.from_entity(course))

    # ---- helpers ---------------------------------------------------------------------------

    async def _load_academy(self, academy_id: Id[Academy]) -> Result[Academy, IDomainError]:
        academy = await self._academies.get(academy_id)
        if academy is None:
            return failure(DomainError.not_found("Academy not found.", code=AcademyErrorCodes.ACADEMY_NOT_FOUND))
        return success(academy)

    async def _load_owned(
        self, academy_id: Id[Academy], course_id: Id[Course]
    ) -> Result[Course, IDomainError]:
        """Another academy's course answers 404 too, so its existence is not revealed."""
        course = await self._courses.get(course_id)
        if course is None or course.academy_id != academy_id:
            return failure(_course_not_found())
        return success(course)

    async def _change(
        self,
        academy_id: Id[Academy],
        course_id: Id[Course],
        action: Callable[[Course, datetime], Result[None, IDomainError]],
    ) -> Result[CourseDto, IDomainError]:
        """Load the course, apply one domain transition, save only if it succeeded."""
        loaded = await self._load_owned(academy_id, course_id)
        if loaded.is_failure:
            return failure(loaded.error)
        course = loaded.value
        changed = action(course, self._time.now())
        if changed.is_failure:
            return failure(changed.error)
        await self._courses.update(course)
        return success(CourseDto.from_entity(course))

    async def _go_live(
        self,
        academy_id: Id[Academy],
        course_id: Id[Course],
        action: Callable[[Course, datetime], Result[None, IDomainError]],
    ) -> Result[CourseDto, IDomainError]:
        """Publish or resume: the academy must not be suspended and the course must not overlap another live one."""
        academy = await self._load_academy(academy_id)
        if academy.is_failure:
            return failure(academy.error)
        can_publish = academy.value.ensure_can_publish()
        if can_publish.is_failure:
            return failure(can_publish.error)

        loaded = await self._load_owned(academy_id, course_id)
        if loaded.is_failure:
            return failure(loaded.error)
        course = loaded.value

        others = await self._courses.list_active_by_academy(academy_id)
        no_overlap = self._overlap_policy.ensure_no_overlap(course, others)
        if no_overlap.is_failure:
            return failure(no_overlap.error)

        changed = action(course, self._time.now())
        if changed.is_failure:
            return failure(changed.error)
        await self._courses.update(course)
        return success(CourseDto.from_entity(course))


def _course_not_found() -> IDomainError:
    return DomainError.not_found("Course not found.", code=CourseErrorCodes.NOT_FOUND)
