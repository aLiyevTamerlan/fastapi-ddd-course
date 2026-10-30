from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from course.common.entity import Entity
from course.common.errors.domain_error import DomainError, IDomainError
from course.common.identity import Id
from course.common.result import Result, failure, success
from course.domain.academy.enums import AcademyStatus
from course.domain.academy.errors import AcademyErrorCodes
from course.domain.academy.value_objects._text import normalize_text
from course.domain.academy.value_objects.academy_name import AcademyName
from course.domain.academy.value_objects.contact_email import ContactEmail


class Academy(Entity["Academy"]):
    """A training academy (course provider). It owns its own profile and status; its courses are separate entities
    that reference it by ``academy_id`` (see ``Course``).

    A new academy is ACTIVE at once and can publish. The verified badge is separate from the status:
    an admin grants it after checking the academy and revokes it when analytics flags fraud.

    Status transitions::

        create --> ACTIVE --suspend--> SUSPENDED --reactivate--> ACTIVE

    Earlier approval flow (kept, not used by ``create``)::

        PENDING_VERIFICATION --verify--> ACTIVE
                 +--reject--> REJECTED
    """

    REJECTION_REASON_MAXIMUM_LENGTH: ClassVar[int] = 500

    def __init__(
        self,
        academy_id: Id[Academy],
        name: AcademyName,
        contact_email: ContactEmail,
        status: AcademyStatus,
        created_at: datetime,
        last_modified_at: datetime,
        rejection_reason: str | None = None,
        is_verified: bool = False,
        verified_at: datetime | None = None,
    ) -> None:
        super().__init__(academy_id, created_at, last_modified_at)
        self._name = name
        self._contact_email = contact_email
        self._status = status
        self._rejection_reason = rejection_reason
        self._is_verified = is_verified
        self._verified_at = verified_at

    # ---- factories -------------------------------------------------------------------------

    @classmethod
    def create(cls, name: str | None, contact_email: str | None, now: datetime) -> Result[Academy, IDomainError]:
        """A newly registered academy is active at once and can publish; it starts without the verified badge."""
        name_result = AcademyName.create(name)
        if name_result.is_failure:
            return failure(name_result.error)

        email_result = ContactEmail.create(contact_email)
        if email_result.is_failure:
            return failure(email_result.error)

        return success(
            cls(Id.new(), name_result.value, email_result.value, AcademyStatus.ACTIVE, now, now)
        )

    @classmethod
    def rehydrate(
        cls,
        *,
        academy_id: uuid.UUID,
        name: str,
        contact_email: str,
        status: str,
        rejection_reason: str | None,
        created_at: datetime,
        last_modified_at: datetime,
        is_verified: bool = False,
        verified_at: datetime | None = None,
    ) -> Academy:
        """Rebuild an academy loaded from storage. Business rules are not re-run; value object
        constructors only reject corrupted data (``InvariantViolationError``)."""
        return cls(
            Id(academy_id),
            AcademyName(name),
            ContactEmail(contact_email),
            AcademyStatus(status),
            created_at,
            last_modified_at,
            rejection_reason,
            is_verified,
            verified_at,
        )

    # ---- properties ------------------------------------------------------------------------

    @property
    def name(self) -> AcademyName:
        return self._name

    @property
    def contact_email(self) -> ContactEmail:
        return self._contact_email

    @property
    def status(self) -> AcademyStatus:
        return self._status

    @property
    def rejection_reason(self) -> str | None:
        return self._rejection_reason

    @property
    def is_verified(self) -> bool:
        return self._is_verified

    @property
    def verified_at(self) -> datetime | None:
        return self._verified_at

    @property
    def can_publish(self) -> bool:
        return self._status is AcademyStatus.ACTIVE

    # ---- behaviour -------------------------------------------------------------------------

    def ensure_can_publish(self) -> Result[None, IDomainError]:
        """Rule used by the application layer before it creates, duplicates, publishes or resumes an
        course for this academy: the academy must be active and carry the verified badge."""
        if self._status is AcademyStatus.SUSPENDED:
            return failure(
                DomainError.conflict(
                    "A suspended academy cannot publish courses.", AcademyErrorCodes.ACADEMY_SUSPENDED
                )
            )
        if not self.can_publish:
            return failure(
                DomainError.conflict(
                    "Only a verified academy can publish courses.", AcademyErrorCodes.ACADEMY_NOT_ACTIVE
                )
            )
        if not self._is_verified:
            return failure(
                DomainError.conflict(
                    "Only an academy with the verified badge can create or publish courses.",
                    AcademyErrorCodes.ACADEMY_NOT_VERIFIED,
                )
            )
        return success(None)

    def rename(self, name: str | None, now: datetime) -> Result[None, IDomainError]:
        name_result = AcademyName.create(name)
        if name_result.is_failure:
            return failure(name_result.error)
        self._name = name_result.value
        self._last_modified_at_utc = now
        return success(None)

    def change_contact_email(self, contact_email: str | None, now: datetime) -> Result[None, IDomainError]:
        email_result = ContactEmail.create(contact_email)
        if email_result.is_failure:
            return failure(email_result.error)
        self._contact_email = email_result.value
        self._last_modified_at_utc = now
        return success(None)

    def verify(self, now: datetime) -> Result[None, IDomainError]:
        """Admin confirmed the academy's registration and tax ID."""
        if self._status is not AcademyStatus.PENDING_VERIFICATION:
            return failure(
                DomainError.conflict(
                    "Only an academy awaiting verification can be verified.",
                    AcademyErrorCodes.ACADEMY_NOT_PENDING_VERIFICATION,
                )
            )
        self._status = AcademyStatus.ACTIVE
        self._last_modified_at_utc = now
        return success(None)

    def reject(self, reason: str | None, now: datetime) -> Result[None, IDomainError]:
        """Admin declined the registration; the reason is sent to the academy."""
        normalized = normalize_text(reason or "")
        if not normalized:
            return failure(
                DomainError.validation("Rejection reason is required.", code=AcademyErrorCodes.INVALID_REJECTION_REASON)
            )
        if len(normalized) > self.REJECTION_REASON_MAXIMUM_LENGTH:
            return failure(
                DomainError.validation(
                    f"Rejection reason cannot exceed {self.REJECTION_REASON_MAXIMUM_LENGTH} characters.",
                    code=AcademyErrorCodes.INVALID_REJECTION_REASON,
                )
            )
        if self._status is not AcademyStatus.PENDING_VERIFICATION:
            return failure(
                DomainError.conflict(
                    "Only an academy awaiting verification can be rejected.",
                    AcademyErrorCodes.ACADEMY_NOT_PENDING_VERIFICATION,
                )
            )
        self._status = AcademyStatus.REJECTED
        self._rejection_reason = normalized
        self._last_modified_at_utc = now
        return success(None)

    def grant_verification(self, now: datetime) -> Result[None, IDomainError]:
        """Admin checked the academy and shows students the verified badge."""
        if self._is_verified:
            return failure(
                DomainError.conflict("Academy is already verified.", AcademyErrorCodes.ACADEMY_ALREADY_VERIFIED)
            )
        if self._status is AcademyStatus.SUSPENDED:
            return failure(
                DomainError.conflict("A suspended academy cannot be verified.", AcademyErrorCodes.ACADEMY_SUSPENDED)
            )
        self._is_verified = True
        self._verified_at = now
        self._last_modified_at_utc = now
        return success(None)

    def revoke_verification(self, now: datetime) -> Result[None, IDomainError]:
        """Admin removes the verified badge, e.g. when fraud analytics flags the academy."""
        if not self._is_verified:
            return failure(DomainError.conflict("Academy is not verified.", AcademyErrorCodes.ACADEMY_NOT_VERIFIED))
        self._is_verified = False
        self._verified_at = None
        self._last_modified_at_utc = now
        return success(None)

    def suspend(self, now: datetime) -> Result[None, IDomainError]:
        if self._status is AcademyStatus.SUSPENDED:
            return failure(
                DomainError.conflict("Academy is already suspended.", AcademyErrorCodes.ACADEMY_ALREADY_SUSPENDED)
            )
        if self._status is not AcademyStatus.ACTIVE:
            return failure(
                DomainError.conflict("Only an active academy can be suspended.", AcademyErrorCodes.ACADEMY_NOT_ACTIVE)
            )
        self._status = AcademyStatus.SUSPENDED
        self._last_modified_at_utc = now
        return success(None)

    def reactivate(self, now: datetime) -> Result[None, IDomainError]:
        if self._status is AcademyStatus.ACTIVE:
            return failure(DomainError.conflict("Academy is already active.", AcademyErrorCodes.ACADEMY_ALREADY_ACTIVE))
        if self._status is not AcademyStatus.SUSPENDED:
            return failure(
                DomainError.conflict(
                    "Only a suspended academy can be reactivated.", AcademyErrorCodes.ACADEMY_NOT_SUSPENDED
                )
            )
        self._status = AcademyStatus.ACTIVE
        self._last_modified_at_utc = now
        return success(None)
