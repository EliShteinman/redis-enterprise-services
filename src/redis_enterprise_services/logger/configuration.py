import logging.config

from pydantic import JsonValue

from redis_enterprise_services.config.service.log_settings import LogFileSettings, LogSettings
from redis_enterprise_services.logger.json_formatter import JsonFormatter
from redis_enterprise_services.logger.quiet import QuietRequestFilter

STREAM_HANDLER_CLASS: str = "logging.StreamHandler"
FILE_HANDLER_CLASS: str = "logging.handlers.RotatingFileHandler"


def configure_logging(*, settings: LogSettings) -> None:
    if settings.file.enabled:
        settings.file.path.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(config=build_logging_dict_config(settings=settings))


def build_logging_dict_config(*, settings: LogSettings) -> dict[str, JsonValue]:
    handlers: dict[str, JsonValue] = {"console": console_handler(settings=settings)}
    if settings.file.enabled:
        handlers["file"] = file_handler(settings=settings.file)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "line": {
                "format": settings.line_format,
                "datefmt": settings.date_format,
                "defaults": dict(settings.line_format_defaults),
            },
            "json": {
                "()": f"{JsonFormatter.__module__}.{JsonFormatter.__qualname__}",
                "dropped_fields": list(settings.json_dropped_fields),
            },
        },
        "filters": {
            "quiet": {
                "()": f"{QuietRequestFilter.__module__}.{QuietRequestFilter.__qualname__}",
                "kept_level": settings.quiet_kept_level,
            }
        },
        "handlers": handlers,
        "root": {"level": settings.level, "handlers": list(handlers)},
        "loggers": {
            name: {"level": settings.level, "handlers": [], "propagate": True}
            for name in settings.root_propagating_loggers
        },
    }


def console_handler(*, settings: LogSettings) -> dict[str, JsonValue]:
    return {
        "class": STREAM_HANDLER_CLASS,
        "formatter": settings.console_format.value,
        "stream": settings.stream,
        "filters": ["quiet"],
    }


def file_handler(*, settings: LogFileSettings) -> dict[str, JsonValue]:
    return {
        "class": FILE_HANDLER_CLASS,
        "formatter": settings.format.value,
        "filename": str(settings.path),
        "maxBytes": settings.max_bytes,
        "backupCount": settings.backup_count,
        "encoding": settings.encoding,
        "filters": ["quiet"],
    }
