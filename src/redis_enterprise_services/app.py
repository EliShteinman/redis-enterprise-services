from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from redis_enterprise_services.api import health
from redis_enterprise_services.config import Settings
from redis_enterprise_services.logger import configure_logging


def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="redis-enterprise-services", lifespan=lifespan)
    app.state.settings = Settings()
    app.include_router(router=health.router)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings=settings.log)
    yield
