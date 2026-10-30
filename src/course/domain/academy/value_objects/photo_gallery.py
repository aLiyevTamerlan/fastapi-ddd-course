from __future__ import annotations
from dataclasses import dataclass

from course.common.errors.domain_error import DomainError
from course.common.result import Result, failure, success
from course.domain.academy.errors import CourseErrorCodes



@dataclass(frozen=True)
class PhotoGallery:
    photos: tuple[str, ...]          # storage keys or URLs, order = display order

    @classmethod
    def create(cls, photos: list[str]) -> Result[PhotoGallery]:
        cleaned = tuple(p.strip() for p in (photos or []) if p and p.strip())
        if not cleaned:                       # can't publish a course with no photos
            return failure(DomainError.validation(
                "At least one photo is required", code=CourseErrorCodes.GALLERY_EMPTY))
        if len(cleaned) > 20:
            return failure(DomainError.validation(
                "Too many photos (max 20)", code=CourseErrorCodes.GALLERY_TOO_LARGE))
        return success(cls(cleaned))

    @property
    def cover(self) -> str:
        return self.photos[0]