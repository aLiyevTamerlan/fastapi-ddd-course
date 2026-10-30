from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from course.common.errors.domain_error import DomainError, InvariantViolationError
from course.common.result import Result, failure, success
from course.domain.academy.errors import AcademyErrorCodes
from course.domain.academy.value_objects._text import normalize_text



@dataclass(frozen=True, slots=True)
class AcademyName:
    MAXIMUM_LENGTH: ClassVar[int] = 200

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or self.value != normalize_text(self.value) or self._validate(self.value):
            raise InvariantViolationError(f"Invalid AcademyName {self.value!r}. Use AcademyName.create().")

    @classmethod
    def create(cls, value: str | None) -> Result[AcademyName, DomainError]:
        normalized = normalize_text(value or "")
        error = cls._validate(normalized)
        if error is not None:
            return failure(error)
        return success(cls(normalized))

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def _validate(cls, normalized: str) -> DomainError | None:
        if not normalized:
            return DomainError.bad_request("Academy name is required.", code=AcademyErrorCodes.INVALID_ACADEMY_NAME)
        if len(normalized) > AcademyName.MAXIMUM_LENGTH:
            return DomainError.validation(
                f"Academy name cannot exceed {AcademyName.MAXIMUM_LENGTH} characters.",
                code=AcademyErrorCodes.INVALID_ACADEMY_NAME,
            )
        return None
