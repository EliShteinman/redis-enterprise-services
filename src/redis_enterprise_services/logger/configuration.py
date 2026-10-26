import logging.config

from pydantic import JsonValue

from redis_enterprise_services.config import LoggingSettings

SERVER_LOGGERS: tuple[str, ...] = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configure_logging(*, settings: LoggingSettings) -> None:
    logging.config.dictConfig(config=logging_config(settings=settings))


def logging_config(*, settings: LoggingSettings) -> dict[str, JsonValue]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"line": {"format": settings.line_pattern, "datefmt": settings.date_format}},
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "line", "stream": "ext://sys.stdout"}
        },
        "root": {"level": settings.level, "handlers": ["console"]},
        "loggers": {name: {"handlers": [], "propagate": True} for name in SERVER_LOGGERS},
    }
