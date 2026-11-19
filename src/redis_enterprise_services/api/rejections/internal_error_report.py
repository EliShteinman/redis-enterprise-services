import logging

from opentelemetry import trace

logger: logging.Logger = logging.getLogger(name=__name__)


def report_internal_error(*, error: BaseException, message: str) -> None:
    logger.error(msg=message, exc_info=error)
    trace.get_current_span().record_exception(exception=error)
