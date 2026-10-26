import uvicorn

from redis_enterprise_services.app import create_app
from redis_enterprise_services.config import Settings
from redis_enterprise_services.logger import configure_logging


def main() -> None:
    settings: Settings = Settings()
    configure_logging(settings=settings.log)
    uvicorn.run(app=create_app(), host=settings.server.host, port=settings.server.port, log_config=None)


if __name__ == "__main__":
    main()
