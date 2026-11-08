import logging
from collections.abc import Callable

from redis_enterprise_services.cluster.safe_to_read_again import is_safe_to_read_again
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

logger: logging.Logger = logging.getLogger(name=__name__)


def tolerate_read_again_errors(
    *, is_done: Callable[[], bool], transient_error_codes: frozenset[str], subject: str
) -> Callable[[], bool]:
    def is_done_or_read_again() -> bool:
        try:
            return is_done()
        except RedisEnterpriseServicesError as error:
            if not is_safe_to_read_again(error=error, transient_error_codes=transient_error_codes):
                raise
            logger.warning(msg=f"reading {subject} failed, it is read again: {error.coded_message()}")
            return False

    return is_done_or_read_again
