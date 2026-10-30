from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from course.application.academy.abstractions.academy_repository import IAcademyRepository
from course.application.academy.dtos.academy_dtos import AcademyDto
from course.common.errors.domain_error import DomainError, IDomainError
from course.common.identity import Id
from course.common.result import Result, failure, success
from course.common.time_provider import TimeProvider
from course.domain.academy.academy import Academy
from course.domain.academy.enums import AcademyStatus
from course.domain.academy.errors import AcademyErrorCodes


class AcademyService:
    """Use cases for academies: load, let the entity decide, save. No business rules live here."""

    def __init__(self, academies: IAcademyRepository, time_provider: TimeProvider) -> None:
        self._academies = academies
        self._time = time_provider

    # ---- academy dashboard ------------------------------------------------------------------

    async def register(self, name: str | None, contact_email: str | None) -> Result[AcademyDto, IDomainError]:
        created = Academy.create(name, contact_email, self._time.now())
        if created.is_failure:
            return failure(created.error)
        academy = created.value
        # Checked after create(), so the values are already normalized (spaces collapsed, email lower-cased).
        unique = await self._ensure_unique(academy.name.value, academy.contact_email.value, excluding=None)
        if unique.is_failure:
            return failure(unique.error)
        await self._academies.add(academy)
        return success(AcademyDto.from_entity(academy))

    async def get(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        loaded = await self._load(academy_id)
        if loaded.is_failure:
            return failure(loaded.error)
        return success(AcademyDto.from_entity(loaded.value))

    async def update_profile(
        self, academy_id: Id[Academy], name: str | None, contact_email: str | None
    ) -> Result[AcademyDto, IDomainError]:
        """Partial update: a field left as ``None`` is not changed."""
        loaded = await self._load(academy_id)
        if loaded.is_failure:
            return failure(loaded.error)
        academy = loaded.value
        now = self._time.now()

        if name is not None:
            renamed = academy.rename(name, now)
            if renamed.is_failure:
                return failure(renamed.error)
        if contact_email is not None:
            changed = academy.change_contact_email(contact_email, now)
            if changed.is_failure:
                return failure(changed.error)

        unique = await self._ensure_unique(
            academy.name.value if name is not None else None,
            academy.contact_email.value if contact_email is not None else None,
            excluding=academy.id,
        )
        if unique.is_failure:
            return failure(unique.error)

        await self._academies.update(academy)
        return success(AcademyDto.from_entity(academy))

    # ---- admin -----------------------------------------------------------------------------

    async def list_by_status(self, status: str | None) -> Result[list[AcademyDto], IDomainError]:
        parsed: AcademyStatus | None = None
        if status is not None:
            try:
                parsed = AcademyStatus.from_name(status)
            except ValueError:
                allowed = ", ".join(s.value for s in AcademyStatus)
                return failure(
                    DomainError.bad_request(
                        f"Unknown academy status {status!r}. Allowed: {allowed}.",
                        code=AcademyErrorCodes.INVALID_ACADEMY_STATUS,
                    )
                )
        academies = await self._academies.list_by_status(parsed)
        return success([AcademyDto.from_entity(a) for a in academies])

    async def verify(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.verify(now))

    async def reject(self, academy_id: Id[Academy], reason: str | None) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.reject(reason, now))

    async def grant_verification(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.grant_verification(now))

    async def revoke_verification(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.revoke_verification(now))

    async def suspend(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.suspend(now))

    async def reactivate(self, academy_id: Id[Academy]) -> Result[AcademyDto, IDomainError]:
        return await self._change(academy_id, lambda academy, now: academy.reactivate(now))

    # ---- helpers ---------------------------------------------------------------------------

    async def _load(self, academy_id: Id[Academy]) -> Result[Academy, IDomainError]:
        academy = await self._academies.get(academy_id)
        if academy is None:
            return failure(DomainError.not_found("Academy not found.", code=AcademyErrorCodes.ACADEMY_NOT_FOUND))
        return success(academy)

    async def _ensure_unique(
        self, name: str | None, contact_email: str | None, excluding: Id[Academy] | None
    ) -> Result[None, IDomainError]:
        """No two academies share a name (case-insensitive) or a contact email. ``None`` skips that check."""
        if name is not None and await self._academies.exists_with_name(name, excluding):
            return failure(
                DomainError.conflict(
                    "An academy with this name already exists.", code=AcademyErrorCodes.ACADEMY_NAME_TAKEN
                )
            )
        if contact_email is not None and await self._academies.exists_with_contact_email(contact_email, excluding):
            return failure(
                DomainError.conflict(
                    "An academy with this contact email already exists.", code=AcademyErrorCodes.CONTACT_EMAIL_TAKEN
                )
            )
        return success(None)

    async def _change(
        self,
        academy_id: Id[Academy],
        action: Callable[[Academy, datetime], Result[None, IDomainError]],
    ) -> Result[AcademyDto, IDomainError]:
        """Load the academy, apply one domain transition, save only if it succeeded."""
        loaded = await self._load(academy_id)
        if loaded.is_failure:
            return failure(loaded.error)
        academy = loaded.value
        changed = action(academy, self._time.now())
        if changed.is_failure:
            return failure(changed.error)
        await self._academies.update(academy)
        return success(AcademyDto.from_entity(academy))
