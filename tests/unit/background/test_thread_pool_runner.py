from concurrent.futures import Future

import pytest

from redis_enterprise_services.background.thread_pool_runner import log_failure


def test_a_task_cancelled_before_it_started_is_logged_as_cancelled(caplog: pytest.LogCaptureFixture) -> None:
    cancelled: Future[object] = Future()
    cancelled.cancel()
    log_failure(name="create orders", done=cancelled)
    assert "create orders was cancelled before it started" in caplog.text
