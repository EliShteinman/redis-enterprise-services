from concurrent.futures import Future

import pytest

from redis_enterprise_services.background.thread_pool_task_runner import log_unsuccessful_end


def test_a_task_cancelled_before_it_started_is_logged_as_cancelled(caplog: pytest.LogCaptureFixture) -> None:
    cancelled: Future[object] = Future()
    cancelled.cancel()
    log_unsuccessful_end(name="create orders", future=cancelled)
    assert "create orders was cancelled before it started" in caplog.text
