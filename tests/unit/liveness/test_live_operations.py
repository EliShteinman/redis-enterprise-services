from collections.abc import Callable
from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.live_operations import LiveOperations


def failing_task() -> object:
    raise RuntimeError("bug")


def test_an_untracked_operation_gets_no_more_heartbeats() -> None:
    heartbeat_store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live_operations: LiveOperations = LiveOperations(heartbeat_store=heartbeat_store)
    live_operations.track(trace_id="trace-1")
    live_operations.track(trace_id="trace-2")
    live_operations.untrack_and_delete_heartbeat(trace_id="trace-1")

    live_operations.refresh_heartbeats()

    heartbeat_store.refresh.assert_called_with(trace_ids=["trace-2"])


def test_an_operation_is_untracked_when_its_task_fails() -> None:
    heartbeat_store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    live_operations: LiveOperations = LiveOperations(heartbeat_store=heartbeat_store)
    live_operations.track(trace_id="trace-1")
    untracking_task: Callable[[], object] = live_operations.untracking_when_done(
        trace_id="trace-1", task=failing_task
    )

    with pytest.raises(expected_exception=RuntimeError):
        untracking_task()

    heartbeat_store.delete.assert_called_once_with(trace_id="trace-1")
