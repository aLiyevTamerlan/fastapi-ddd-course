from __future__ import annotations

from abc import ABC, abstractmethod

from course.common.identity import Id
from course.domain.academy.academy import Academy
from course.domain.academy.enums import AcademyStatus


class IAcademyRepository(ABC):
    """Port for academy storage. Lives in the application layer because its methods are ``async``;
    the implementation (``AcademyRepository``) lives in infrastructure."""

    @abstractmethod
    async def add(self, academy: Academy) -> None: ...

    @abstractmethod
    async def update(self, academy: Academy) -> None: ...

    @abstractmethod
    async def get(self, academy_id: Id[Academy]) -> Academy | None: ...

    @abstractmethod
    async def list_by_status(self, status: AcademyStatus | None) -> list[Academy]:
        """Oldest first, so the verification queue is handled in arrival order. ``None`` lists all."""

    @abstractmethod
    async def exists_with_name(self, name: str, excluding: Id[Academy] | None = None) -> bool:
        """Another academy already uses ``name`` (case-insensitive). ``excluding`` skips that academy itself."""

    @abstractmethod
    async def exists_with_contact_email(self, contact_email: str, excluding: Id[Academy] | None = None) -> bool:
        """Another academy already uses ``contact_email``. ``excluding`` skips that academy itself."""
