from collections.abc import Callable
from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.live_operations import LiveOperations


def failing_task() -> object:
    raise RuntimeError("bug")


def test_an_untracked_operation_gets_no_more_heartbeats() -> None:
    store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live: LiveOperations = LiveOperations(store=store)
    live.track(trace_id="trace-1")
    live.track(trace_id="trace-2")
    live.untrack(trace_id="trace-1")

    live.beat_all()

    store.refresh.assert_called_with(trace_ids=["trace-2"])


def test_an_operation_is_untracked_when_its_task_fails() -> None:
    store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live: LiveOperations = LiveOperations(store=store)
    live.track(trace_id="trace-1")
    task: Callable[[], object] = live.untracked_when_done(trace_id="trace-1", task=failing_task)

    with pytest.raises(expected_exception=RuntimeError):
        task()

    store.delete.assert_called_once_with(trace_id="trace-1")
