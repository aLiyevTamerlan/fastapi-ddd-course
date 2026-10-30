from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from course.common.errors.domain_error import DomainError
from course.common.result import Result, failure, success
from course.domain.academy.errors import CourseErrorCodes

@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    @classmethod
    def create(cls, start: date, end: date) -> Result[DateRange]:
        if start is None or end is None:
            return failure(DomainError.validation(
                "Start and end dates are required",
                code=CourseErrorCodes.DATE_RANGE_INVALID))

        if end < start:
            return failure(DomainError.validation(
                "End date cannot be before start date",
                code=CourseErrorCodes.DATE_RANGE_INVALID))

        return success(cls(start, end))

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end

    def is_in_future(self, today: date) -> bool:
        return self.start > today