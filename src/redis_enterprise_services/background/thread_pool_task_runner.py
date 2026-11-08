import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import Context, copy_context

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.config.background_settings import BackgroundSettings

logger: logging.Logger = logging.getLogger(name=__name__)


class ThreadPoolTaskRunner(BackgroundTaskRunner):
    def __init__(self, *, settings: BackgroundSettings) -> None:
        self._pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=settings.max_workers)

    def submit(self, *, name: str, task: Callable[[], object]) -> None:
        context: Context = copy_context()
        future: Future[object] = self._pool.submit(context.run, task)
        future.add_done_callback(lambda future: context.run(log_unsuccessful_end, name=name, future=future))
        logger.info(msg=f"{name} runs in the background")

    def shutdown(self) -> None:
        logger.info(msg="cancelling the queued background tasks and waiting for the running ones to end")
        self._pool.shutdown(wait=True, cancel_futures=True)


def log_unsuccessful_end(*, name: str, future: Future[object]) -> None:
    if future.cancelled():
        logger.warning(msg=f"{name} was cancelled before it started, it is left to the abandoned sweep")
        return
    error: BaseException | None = future.exception()
    if error is not None:
        logger.critical(msg=f"{name} failed in the background", exc_info=error)
