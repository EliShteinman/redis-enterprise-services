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

    def submit(self, *, task_name: str, task: Callable[[], object]) -> None:
        submitter_context: Context = copy_context()
        future: Future[object] = self._pool.submit(submitter_context.run, task)
        future.add_done_callback(task_outcome_logger(context=submitter_context, task_name=task_name))
        logger.info(msg=f"{task_name} is queued to run in the background")

    def close(self) -> None:
        logger.info(
            msg="closing the background runner: cancelling the queued tasks, waiting for the running ones"
        )
        self._pool.shutdown(wait=True, cancel_futures=True)


def task_outcome_logger(*, context: Context, task_name: str) -> Callable[[Future[object]], None]:
    def log_outcome_in_context(finished_future: Future[object]) -> None:
        context.run(log_task_outcome, task_name=task_name, future=finished_future)

    return log_outcome_in_context


def log_task_outcome(*, task_name: str, future: Future[object]) -> None:
    if future.cancelled():
        logger.warning(msg=f"{task_name} was cancelled before it started, it is left to the abandoned sweep")
        return
    error: BaseException | None = future.exception()
    if error is not None:
        logger.critical(msg=f"{task_name} failed in the background", exc_info=error)
