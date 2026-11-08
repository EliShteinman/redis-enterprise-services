import logging.config

from pydantic import JsonValue

from redis_enterprise_services.config.log_settings import LogSettings

STREAM_HANDLER: str = "logging.StreamHandler"


def configure_logging(*, settings: LogSettings) -> None:
    logging.config.dictConfig(config=logging_config(settings=settings))


def logging_config(*, settings: LogSettings) -> dict[str, JsonValue]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "line": {
                "format": settings.line_pattern,
                "datefmt": settings.date_format,
                "defaults": dict(settings.field_defaults),
            }
        },
        "handlers": {"console": {"class": STREAM_HANDLER, "formatter": "line", "stream": settings.stream}},
        "root": {"level": settings.level, "handlers": ["console"]},
        "loggers": {
            name: {"level": settings.level, "handlers": [], "propagate": True}
            for name in settings.server_loggers
        },
    }
