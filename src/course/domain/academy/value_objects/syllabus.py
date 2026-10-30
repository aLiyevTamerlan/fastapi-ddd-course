from __future__ import annotations
from dataclasses import dataclass

from course.common.errors.domain_error import DomainError
from course.common.result import Result, failure, success
from course.domain.academy.errors import CourseErrorCodes

@dataclass(frozen=True)
class SyllabusItem:
    order: int
    title: str
    detail: str


@dataclass(frozen=True)
class Syllabus:
    items: tuple[SyllabusItem, ...]

    @classmethod
    def create(cls, items: list[SyllabusItem]) -> "Result[Syllabus]":
        if not items:
            return failure(DomainError.validation(
                "Syllabus needs at least one topic", code=CourseErrorCodes.SYLLABUS_EMPTY))
        ordered = tuple(sorted(items, key=lambda i: i.order))
        return success(cls(ordered))