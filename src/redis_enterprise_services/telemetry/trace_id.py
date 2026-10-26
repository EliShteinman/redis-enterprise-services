from opentelemetry import trace


def current_trace_id() -> str:
    return format(trace.get_current_span().get_span_context().trace_id, "032x")
