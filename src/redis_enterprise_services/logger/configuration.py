import logging.config

from pydantic import JsonValue

from redis_enterprise_services.config.log_settings import LogSettings

STREAM_HANDLER_CLASS: str = "logging.StreamHandler"


def configure_logging(*, settings: LogSettings) -> None:
    logging.config.dictConfig(config=build_logging_dict_config(settings=settings))


def build_logging_dict_config(*, settings: LogSettings) -> dict[str, JsonValue]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "line": {
                "format": settings.line_pattern,
                "datefmt": settings.date_format,
                "defaults": dict(settings.line_pattern_defaults),
            }
        },
        "handlers": {
            "console": {"class": STREAM_HANDLER_CLASS, "formatter": "line", "stream": settings.stream}
        },
        "root": {"level": settings.level, "handlers": ["console"]},
        "loggers": {
            name: {"level": settings.level, "handlers": [], "propagate": True}
            for name in settings.server_loggers
        },
    }
