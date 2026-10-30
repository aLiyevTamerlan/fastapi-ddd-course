from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import ClassVar

from course.common.errors.domain_error import DomainError, InvariantViolationError
from course.common.result import Result, failure, success
from course.domain.academy.errors import CourseErrorCodes


@dataclass(frozen=True, slots=True)
class RefundTier:
    """``days_before`` or more days before the course starts, the student gets ``refund_percent`` back."""

    days_before: int
    refund_percent: int


@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    """The academy's own cancellation rules for one course, chosen when it is published.

    Example: tiers ``(10 → 100%, 5 → 50%)`` with ``last_cancellation_days_before = 5`` means
    12 days before: 100%; 7 days before: 50%; 4 days before: the student can no longer cancel.
    Days between the lowest tier and the last cancellation day refund 0%.
    """

    MAXIMUM_TIERS: ClassVar[int] = 10

    tiers: tuple[RefundTier, ...]  # sorted by days_before, highest first
    last_cancellation_days_before: int

    def __post_init__(self) -> None:
        if self._validate(self.tiers, self.last_cancellation_days_before) is not None:
            raise InvariantViolationError("Invalid CancellationPolicy. Use CancellationPolicy.create().")

    @classmethod
    def create(
        cls, tiers: Sequence[RefundTier], last_cancellation_days_before: int
    ) -> Result[CancellationPolicy, DomainError]:
        ordered = tuple(sorted(tiers, key=lambda t: t.days_before, reverse=True))
        error = cls._validate(ordered, last_cancellation_days_before)
        if error is not None:
            return failure(error)
        return success(cls(ordered, last_cancellation_days_before))

    def refund_percent_for(self, days_before: int) -> int | None:
        """Percent refunded when cancelling ``days_before`` days before the start; ``None`` if too late to cancel."""
        if days_before < self.last_cancellation_days_before:
            return None
        for tier in self.tiers:
            if days_before >= tier.days_before:
                return tier.refund_percent
        return 0

    @classmethod
    def _validate(cls, tiers: tuple[RefundTier, ...], last_cancellation_days_before: int) -> DomainError | None:
        def invalid(message: str) -> DomainError:
            return DomainError.validation(message, code=CourseErrorCodes.CANCELLATION_INVALID)

        if last_cancellation_days_before < 0:
            return invalid("The last cancellation day must be zero or more days before the course.")
        if len(tiers) > cls.MAXIMUM_TIERS:
            return invalid(f"A cancellation policy can have at most {cls.MAXIMUM_TIERS} refund tiers.")
        for tier in tiers:
            if tier.days_before < 0:
                return invalid("Refund tier days must be zero or more.")
            if not 0 <= tier.refund_percent <= 100:
                return invalid("Refund percent must be between 0 and 100.")
        for higher, lower in pairwise(tiers):
            if higher.days_before == lower.days_before:
                return invalid(f"Two refund tiers start at {higher.days_before} days.")
            if lower.refund_percent > higher.refund_percent:
                return invalid("Refund percent cannot grow as the course gets closer.")
        return None
