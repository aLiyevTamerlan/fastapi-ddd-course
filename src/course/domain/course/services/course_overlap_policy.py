from __future__ import annotations

from collections.abc import Iterable

from course.common.errors.domain_error import DomainError, IDomainError
from course.common.result import Result, failure, success
from course.domain.academy.course import Course
from course.domain.academy.errors import CourseErrorCodes


class CourseOverlapPolicy:
    """One academy cannot run two live courses with the same title on overlapping dates.

    The rule compares a candidate with the academy's other courses, so no single entity owns it.
    The application layer loads the list; this policy only decides."""

    def ensure_no_overlap(
        self, candidate: Course, others: Iterable[Course]
    ) -> Result[None, IDomainError]:
        title = candidate.title.casefold()
        for other in others:
            if (
                other.id != candidate.id
                and other.academy_id == candidate.academy_id
                and other.is_active
                and other.title.casefold() == title
                and other.dates.overlaps(candidate.dates)
            ):
                return failure(
                    DomainError.conflict(
                        f"The academy already has a live course “{other.title}” on overlapping dates "
                        f"({other.start_date} - {other.end_date}).",
                        code=CourseErrorCodes.OVERLAP,
                    )
                )
        return success(None)
