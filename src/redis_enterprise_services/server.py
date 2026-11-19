import uvicorn

from redis_enterprise_services.app import create_app
from redis_enterprise_services.config.settings import Settings


def serve(*, settings: Settings) -> None:
    uvicorn.run(
        app=create_app(settings=settings),
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,
    )
