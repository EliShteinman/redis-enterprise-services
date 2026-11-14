from contextvars import ContextVar, Token

from redis_enterprise_services.background.thread_pool_task_runner import ThreadPoolTaskRunner
from redis_enterprise_services.config.background_settings import BackgroundSettings

REQUEST_TRACE: ContextVar[str] = ContextVar("request_trace", default="none")


def test_a_background_task_runs_in_the_context_of_the_request_that_submitted_it() -> None:
    seen: list[str] = []
    runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=BackgroundSettings(max_workers=1))
    token: Token[str] = REQUEST_TRACE.set("trace-1")

    runner.submit(task_name="create orders", task=lambda: seen.append(REQUEST_TRACE.get()))
    runner.close()
    REQUEST_TRACE.reset(token)

    assert seen == ["trace-1"]
