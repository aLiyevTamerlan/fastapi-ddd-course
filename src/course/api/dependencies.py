from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from course.application.academy.academy_service import AcademyService
from course.application.academy.course_service import CourseService
from course.infrastructure.academy.academy_repository import AcademyRepository
from course.infrastructure.academy.course_repository import CourseRepository
from course.infrastructure.system_time_provider import SystemTimeProvider


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One ``AsyncSession`` per request, closed when the request ends."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_academy_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AcademyService:
    return AcademyService(AcademyRepository(session), SystemTimeProvider())


def get_course_service(session: Annotated[AsyncSession, Depends(get_session)]) -> CourseService:
    return CourseService(AcademyRepository(session), CourseRepository(session), SystemTimeProvider())


AcademyServiceDep = Annotated[AcademyService, Depends(get_academy_service)]
CourseServiceDep = Annotated[CourseService, Depends(get_course_service)]
