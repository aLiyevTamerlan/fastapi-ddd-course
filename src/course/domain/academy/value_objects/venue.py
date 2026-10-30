from __future__ import annotations
from dataclasses import dataclass
from datetime import time

from course.common.errors.domain_error import DomainError
from course.common.result import Result, failure, success
from course.domain.academy.errors import CourseErrorCodes



@dataclass(frozen=True)
class Venue:
    address: str
    class_time: time

    @classmethod
    def create(cls, address: str, class_time: time) -> Result[Venue]:
        address = (address or "").strip()
        if not address:
            return failure(DomainError.validation(
                "Venue is required", code=CourseErrorCodes.VENUE_EMPTY))
        return success(cls(address, class_time))