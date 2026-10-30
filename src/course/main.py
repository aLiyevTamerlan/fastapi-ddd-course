from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from course.api.academy.academy_router import admin_router as admin_academy_router
from course.api.academy.academy_router import router as academy_router
from course.api.academy.course_router import public_router as public_course_router
from course.api.academy.course_router import router as course_router
from course.infrastructure.config import Settings
from course.infrastructure.database import create_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Composition root: wires the layers together. Run with ``uv run uvicorn marketplace.main:app``."""
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(app_settings.database_url, echo=app_settings.database_echo)
        app.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Marketplace API", lifespan=lifespan)
    app.include_router(academy_router)
    app.include_router(admin_academy_router)
    app.include_router(course_router)
    app.include_router(public_course_router)
    return app


app = create_app()
