import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import Context, copy_context

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.config.background_settings import BackgroundSettings

logger: logging.Logger = logging.getLogger(name=__name__)


class ThreadPoolRunner(TaskRunner):
    def __init__(self, *, settings: BackgroundSettings) -> None:
        self._pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=settings.max_workers)

    def submit(self, *, name: str, task: Callable[[], object]) -> None:
        context: Context = copy_context()
        future: Future[object] = self._pool.submit(context.run, task)
        future.add_done_callback(lambda done: log_failure(name=name, done=done))
        logger.info(msg=f"{name} runs in the background")

    def shutdown(self) -> None:
        logger.info(msg="waiting for the background tasks to end")
        self._pool.shutdown(wait=True)


def log_failure(*, name: str, done: Future[object]) -> None:
    error: BaseException | None = done.exception()
    if error is not None:
        logger.critical(msg=f"{name} failed in the background", exc_info=error)
