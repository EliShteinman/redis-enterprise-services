import logging
from collections.abc import Callable

from redis_enterprise_services.cluster.safe_to_read_again import is_safe_to_read_again
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

logger: logging.Logger = logging.getLogger(name=__name__)


class ToleratedReads:
    def __init__(
        self, *, is_done: Callable[[], bool], transient_error_codes: frozenset[str], subject: str
    ) -> None:
        self._is_done: Callable[[], bool] = is_done
        self._transient_error_codes: frozenset[str] = transient_error_codes
        self._subject: str = subject
        self._any_read_succeeded: bool = False
        self._last_read_error: RedisEnterpriseServicesError | None = None

    def is_done_tolerating_read_again_errors(self) -> bool:
        try:
            done: bool = self._is_done()
        except RedisEnterpriseServicesError as error:
            if not is_safe_to_read_again(error=error, transient_error_codes=self._transient_error_codes):
                raise
            logger.warning(msg=f"reading {self._subject} failed, it is read again: {error.coded_message()}")
            self._last_read_error = error
            return False
        self._any_read_succeeded = True
        return done

    def raise_last_error_if_no_read_succeeded(self) -> None:
        if self._any_read_succeeded or self._last_read_error is None:
            return
        logger.warning(msg=f"no read of {self._subject} succeeded in time, its last read error is reported")
        raise self._last_read_error
