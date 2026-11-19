import logging
from collections.abc import Callable

logger: logging.Logger = logging.getLogger(name=__name__)


class LockAttempts:
    def __init__(self, *, lock_keys: list[str], try_acquire: Callable[[], str | None]) -> None:
        self._lock_keys: list[str] = lock_keys
        self._try_acquire: Callable[[], str | None] = try_acquire
        self._last_holder: str | None = None

    @property
    def last_holder(self) -> str | None:
        return self._last_holder

    def acquired_now(self) -> bool:
        holder: str | None = self._try_acquire()
        if is_first_wait(holder=holder, last_holder=self._last_holder):
            logger.warning(msg=f"{self._lock_keys} locked by {holder}, waiting")
        self._last_holder = holder
        return holder is None


def is_first_wait(*, holder: str | None, last_holder: str | None) -> bool:
    return holder is not None and last_holder is None
