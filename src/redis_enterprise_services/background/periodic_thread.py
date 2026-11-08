import logging
from collections.abc import Callable
from threading import Event, Thread

logger: logging.Logger = logging.getLogger(name=__name__)


class PeriodicThread:
    def __init__(self, *, name: str, interval_seconds: float, task: Callable[[], None]) -> None:
        self._name: str = name
        self._interval_seconds: float = interval_seconds
        self._task: Callable[[], None] = task
        self._stop_requested: Event = Event()
        self._thread: Thread = Thread(target=self._run_every_interval_until_stopped, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()
        logger.info(msg=f"{self._name} runs every {self._interval_seconds} seconds")

    def stop(self) -> None:
        self._stop_requested.set()
        self._thread.join()
        logger.info(msg=f"{self._name} stopped")

    def _run_every_interval_until_stopped(self) -> None:
        while not self._stop_requested.wait(timeout=self._interval_seconds):
            self._run_once_surviving_failure()

    def _run_once_surviving_failure(self) -> None:
        try:
            self._task()
        except Exception:
            logger.exception(msg=f"{self._name} failed, it runs again in {self._interval_seconds} seconds")
