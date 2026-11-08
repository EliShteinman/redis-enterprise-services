import logging

from opentelemetry import trace
from opentelemetry.trace import SpanContext

from redis_enterprise_services.exceptions.telemetry import NoActiveTraceError

logger: logging.Logger = logging.getLogger(name=__name__)


def current_trace_id() -> str:
    span_context: SpanContext = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        logger.critical(msg="no active trace, so this request has no trace id to identify it")
        raise NoActiveTraceError(message="no active trace")
    return format(span_context.trace_id, "032x")


def current_trace_id_or_zeros() -> str:
    return format(trace.get_current_span().get_span_context().trace_id, "032x")
