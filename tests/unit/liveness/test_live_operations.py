from collections.abc import Callable
from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.live_operations import LiveOperations


def fail() -> object:
    raise RuntimeError("bug")


def test_a_released_operation_gets_no_more_heartbeats() -> None:
    store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live: LiveOperations = LiveOperations(store=store)
    live.track(trace_id="trace-1")
    live.track(trace_id="trace-2")
    live.release(trace_id="trace-1")

    live.beat_all()

    store.beat.assert_called_with(trace_ids=["trace-2"])


def test_an_operation_is_released_when_its_task_fails() -> None:
    store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live: LiveOperations = LiveOperations(store=store)
    live.track(trace_id="trace-1")
    task: Callable[[], object] = live.released_after(trace_id="trace-1", task=fail)

    with pytest.raises(expected_exception=RuntimeError):
        task()

    store.stop.assert_called_once_with(trace_id="trace-1")
