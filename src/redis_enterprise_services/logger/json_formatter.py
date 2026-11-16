import json
import logging
import traceback
from collections.abc import Collection
from datetime import UTC, datetime

from pydantic import JsonValue

NO_TRACE: str = "0"
TRACE_FIELDS: dict[str, str] = {"trace_id": "otelTraceID", "span_id": "otelSpanID"}
STANDARD_RECORD_FIELDS: frozenset[str] = frozenset(vars(logging.makeLogRecord(dict={}))) | {
    "message",
    "asctime",
    "otelTraceID",
    "otelSpanID",
    "otelTraceSampled",
    "otelServiceName",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, *, dropped_fields: Collection[str]) -> None:
        super().__init__()
        self._excluded_from_extra: frozenset[str] = STANDARD_RECORD_FIELDS | frozenset(dropped_fields)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, JsonValue] = payload_of(
            record=record, excluded_from_extra=self._excluded_from_extra
        )
        return json.dumps(obj=payload, ensure_ascii=False, default=str)


def payload_of(*, record: logging.LogRecord, excluded_from_extra: frozenset[str]) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    payload |= trace_fields_of(record=record)
    if extra := extra_fields_of(record=record, excluded_from_extra=excluded_from_extra):
        payload["extra"] = extra
    if record.exc_info:
        payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
    if record.stack_info:
        payload["stack"] = record.stack_info
    return payload


def trace_fields_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    fields: dict[str, str] = {
        name: getattr(record, source, NO_TRACE) for name, source in TRACE_FIELDS.items()
    }
    return {name: value for name, value in fields.items() if value != NO_TRACE}


def extra_fields_of(
    *, record: logging.LogRecord, excluded_from_extra: frozenset[str]
) -> dict[str, JsonValue]:
    return {name: value for name, value in vars(record).items() if name not in excluded_from_extra}
