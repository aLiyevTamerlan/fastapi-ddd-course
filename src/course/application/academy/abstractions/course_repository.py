from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from course.common.identity import Id
from course.domain.academy.academy import Academy
from course.domain.academy.course import Course


class ICourseRepository(ABC):
    """Port for course storage; the implementation (``CourseRepository``) lives in infrastructure."""

    @abstractmethod
    async def add(self, course: Course) -> None: ...

    @abstractmethod
    async def update(self, course: Course) -> None: ...

    @abstractmethod
    async def get(self, course_id: Id[Course]) -> Course | None: ...

    @abstractmethod
    async def list_by_academy(self, academy_id: Id[Academy]) -> list[Course]:
        """Every course of the academy except archived ones, soonest start first."""

    @abstractmethod
    async def list_active_by_academy(self, academy_id: Id[Academy]) -> list[Course]:
        """Published or paused courses of the academy (input for the overlap rule)."""

    @abstractmethod
    async def list_published(self, starting_after: date) -> list[Course]:
        """Published courses that start after ``starting_after``, soonest first (public listing)."""
