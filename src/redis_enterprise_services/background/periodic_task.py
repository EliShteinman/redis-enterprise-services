import logging
from collections.abc import Callable
from threading import Event, Thread

logger: logging.Logger = logging.getLogger(name=__name__)


class PeriodicTask:
    def __init__(self, *, name: str, interval_seconds: float, action: Callable[[], None]) -> None:
        self._name: str = name
        self._interval_seconds: float = interval_seconds
        self._action: Callable[[], None] = action
        self._stopped: Event = Event()
        self._thread: Thread = Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()
        logger.info(msg=f"{self._name} runs every {self._interval_seconds} seconds")

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join()
        logger.info(msg=f"{self._name} stopped")

    def _run(self) -> None:
        while not self._stopped.wait(timeout=self._interval_seconds):
            try:
                self._action()
            except Exception:
                logger.exception(
                    msg=f"{self._name} failed, it runs again in {self._interval_seconds} seconds"
                )
