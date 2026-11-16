import json
import logging

from pydantic import JsonValue

from redis_enterprise_services.logger.json_formatter import JsonFormatter


def formatted(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    return json.loads(JsonFormatter(dropped_fields=["color_message"]).format(record=record))


def a_record(**fields: object) -> logging.LogRecord:
    return logging.makeLogRecord(dict={"name": "service", "levelname": "INFO", "msg": "created", **fields})


def test_a_record_holds_the_fields_the_collector_parses() -> None:
    assert formatted(record=a_record()).keys() == {"timestamp", "level", "logger", "message"}


def test_the_trace_of_the_record_is_kept() -> None:
    record: logging.LogRecord = a_record(
        otelTraceID="4bf92f3577b34da6a3ce929d0e0e4736", otelSpanID="00f067aa0ba902b7"
    )

    assert formatted(record=record)["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_a_record_outside_a_trace_has_no_trace_fields() -> None:
    record: logging.LogRecord = a_record(otelTraceID="0", otelSpanID="0")

    assert "trace_id" not in formatted(record=record)


def test_extra_fields_are_kept_under_extra() -> None:
    assert formatted(record=a_record(operation_id="op-1"))["extra"] == {"operation_id": "op-1"}


def test_a_dropped_field_is_left_out_of_extra() -> None:
    assert "extra" not in formatted(record=a_record(color_message="\x1b[36mcreated\x1b[0m"))


def test_the_stack_of_the_record_is_kept() -> None:
    record: logging.LogRecord = a_record(stack_info="Stack (most recent call last):")

    assert formatted(record=record)["stack"] == "Stack (most recent call last):"
