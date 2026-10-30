from __future__ import annotations

from fastapi import APIRouter, Response, status

from course.api.academy.schemas import RegisterAcademyRequest, RejectAcademyRequest, UpdateAcademyRequest
from course.api.dependencies import AcademyServiceDep
from course.api.errors import unwrap
from course.application.academy.dtos.academy_dtos import AcademyDto
from course.common.identity import Id
from course.domain.academy.academy import Academy

# Routers only parse input, call the service and turn the Result into HTTP. No business conditions here.

router = APIRouter(prefix="/api/v1/academies", tags=["academies"])
admin_router = APIRouter(prefix="/api/v1/admin/academies", tags=["admin: academies"])


# ---- academy dashboard ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_academy(body: RegisterAcademyRequest, response: Response, service: AcademyServiceDep) -> AcademyDto:
    academy = unwrap(await service.register(body.name, body.contact_email))
    response.headers["Location"] = f"{router.prefix}/{academy.id}"
    return academy


@router.get("/{academy_id}")
async def get_academy(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.get(parsed))


@router.patch("/{academy_id}")
async def update_academy(academy_id: str, body: UpdateAcademyRequest, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.update_profile(parsed, body.name, body.contact_email))


# ---- admin ---------------------------------------------------------------------------------


@admin_router.get("")
async def list_academies(service: AcademyServiceDep, status: str | None = None) -> list[AcademyDto]:
    """Verification queue: ``?status=PendingVerification``."""
    return unwrap(await service.list_by_status(status))


@admin_router.post("/{academy_id}/verify")
async def verify_academy(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.verify(parsed))


@admin_router.post("/{academy_id}/reject")
async def reject_academy(academy_id: str, body: RejectAcademyRequest, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.reject(parsed, body.reason))


@admin_router.post("/{academy_id}/verified-badge")
async def grant_verified_badge(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.grant_verification(parsed))


@admin_router.delete("/{academy_id}/verified-badge")
async def revoke_verified_badge(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.revoke_verification(parsed))


@admin_router.post("/{academy_id}/suspend")
async def suspend_academy(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.suspend(parsed))


@admin_router.post("/{academy_id}/reactivate")
async def reactivate_academy(academy_id: str, service: AcademyServiceDep) -> AcademyDto:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.reactivate(parsed))
