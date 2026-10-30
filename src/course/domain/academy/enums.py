from __future__ import annotations

from enum import Enum, unique


@unique
class AcademyStatus(Enum):
    """Lifecycle of an academy. A new academy is active at once; PENDING_VERIFICATION and REJECTED belong
    to the earlier approval flow."""

    PENDING_VERIFICATION = "PendingVerification"
    ACTIVE = "Active"
    REJECTED = "Rejected"
    SUSPENDED = "Suspended"

    @classmethod
    def from_name(cls, name: str) -> AcademyStatus:
        return cls(name)


@unique
class CourseStatus(Enum):
    """Lifecycle of a course. The academy moves it through every state itself; there is no moderation.

    DRAFT --publish--> PUBLISHED <--resume-- PAUSED
                          |  +----pause--------^
                          +--cancel--> CANCELLED      (any non-archived state) --archive--> ARCHIVED
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    ARCHIVED  = "archived"