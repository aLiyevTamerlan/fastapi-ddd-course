from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from course.common.errors.domain_error import DomainError, InvariantViolationError
from course.common.result import Result, failure, success
from course.domain.academy.errors import AcademyErrorCodes


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class ContactEmail:
    MAXIMUM_LENGTH: ClassVar[int] = 254

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or self.value != self.value.strip().lower() or self._validate(self.value):
            raise InvariantViolationError(f"Invalid ContactEmail {self.value!r}. Use ContactEmail.create().")

    @classmethod
    def create(cls, value: str | None) -> Result[ContactEmail, DomainError]:
        normalized = (value or "").strip().lower()
        error = cls._validate(normalized)
        if error is not None:
            return failure(error)
        return success(cls(normalized))

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def _validate(cls, normalized: str) -> DomainError | None:
        if not normalized:
            return DomainError.bad_request("Contact email is required.", code=AcademyErrorCodes.INVALID_CONTACT_EMAIL)
        if len(normalized) > cls.MAXIMUM_LENGTH or not _EMAIL_PATTERN.match(normalized):
            return DomainError.validation("Contact email is invalid.", code=AcademyErrorCodes.INVALID_CONTACT_EMAIL)
        return None