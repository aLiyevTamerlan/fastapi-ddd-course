from __future__ import annotations

from fastapi import APIRouter, Response, status

from course.api.dependencies import CourseServiceDep
from course.api.errors import unwrap
from course.application.academy.dtos.course_dtos import (
    CourseDto,
    CreateCourseCommand,
    DuplicateCourseCommand,
)
from course.common.identity import Id
from course.domain.academy.academy import Academy
from course.domain.academy.course import Course

# Routers only parse input, call the service and turn the Result into HTTP. No business conditions here.

router = APIRouter(prefix="/api/v1/academies/{academy_id}/courses", tags=["courses"])
public_router = APIRouter(prefix="/api/v1/public/courses", tags=["public: courses"])


def _ids(academy_id: str, course_id: str) -> tuple[Id[Academy], Id[Course]]:
    return unwrap(Id[Academy].parse(academy_id)), unwrap(Id[Course].parse(course_id))


# ---- academy dashboard ----------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_course(
    academy_id: str, body: CreateCourseCommand, response: Response, service: CourseServiceDep
) -> CourseDto:
    """Creates a draft. Publish it with ``POST .../{course_id}/publish``."""
    parsed = unwrap(Id[Academy].parse(academy_id))
    course = unwrap(await service.create(parsed, body))
    response.headers["Location"] = f"/api/v1/academies/{academy_id}/courses/{course.id}"
    return course


@router.get("")
async def list_courses(academy_id: str, service: CourseServiceDep) -> list[CourseDto]:
    parsed = unwrap(Id[Academy].parse(academy_id))
    return unwrap(await service.list_for_academy(parsed))


@router.get("/{course_id}")
async def get_course(academy_id: str, course_id: str, service: CourseServiceDep) -> CourseDto:
    return unwrap(await service.get(*_ids(academy_id, course_id)))


@router.post("/{course_id}/publish")
async def publish_course(
    academy_id: str, course_id: str, service: CourseServiceDep
) -> CourseDto:
    return unwrap(await service.publish(*_ids(academy_id, course_id)))


@router.post("/{course_id}/pause")
async def pause_course(academy_id: str, course_id: str, service: CourseServiceDep) -> CourseDto:
    return unwrap(await service.pause(*_ids(academy_id, course_id)))


@router.post("/{course_id}/resume")
async def resume_course(
    academy_id: str, course_id: str, service: CourseServiceDep
) -> CourseDto:
    return unwrap(await service.resume(*_ids(academy_id, course_id)))


@router.post("/{course_id}/cancel")
async def cancel_course(
    academy_id: str, course_id: str, service: CourseServiceDep
) -> CourseDto:
    return unwrap(await service.cancel(*_ids(academy_id, course_id)))



@router.delete("/{course_id}")
async def archive_course(
    academy_id: str, course_id: str, service: CourseServiceDep
) -> CourseDto:
    """Archives instead of deleting, so old enrollments keep their reference."""
    return unwrap(await service.archive(*_ids(academy_id, course_id)))


# ---- public (students) --------------------------------------------------------------------


@public_router.get("")
async def list_published_courses(service: CourseServiceDep) -> list[CourseDto]:
    """Upcoming published courses, soonest first."""
    return unwrap(await service.list_published())


@public_router.get("/{course_id}")
async def get_published_course(course_id: str, service: CourseServiceDep) -> CourseDto:
    parsed = unwrap(Id[Course].parse(course_id))
    return unwrap(await service.get_published(parsed))
