from collections.abc import Callable
from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.in_process_operation_heartbeats import InProcessOperationHeartbeats


def failing_task() -> object:
    raise RuntimeError("bug")


def test_an_untracked_operation_gets_no_more_heartbeats() -> None:
    heartbeat_store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    operation_heartbeats: InProcessOperationHeartbeats = InProcessOperationHeartbeats(
        heartbeat_store=heartbeat_store
    )
    operation_heartbeats.track(trace_id="trace-1")
    operation_heartbeats.track(trace_id="trace-2")
    operation_heartbeats.untrack_and_delete_heartbeat(trace_id="trace-1")

    operation_heartbeats.mark_tracked_alive()

    heartbeat_store.mark_alive.assert_called_with(trace_ids=["trace-2"])


def test_an_operation_is_untracked_when_its_task_fails() -> None:
    heartbeat_store: MagicMock = create_autospec(spec=HeartbeatStore, instance=True)
    operation_heartbeats: InProcessOperationHeartbeats = InProcessOperationHeartbeats(
        heartbeat_store=heartbeat_store
    )
    operation_heartbeats.track(trace_id="trace-1")
    untracking_task: Callable[[], object] = operation_heartbeats.untracking_and_deleting_heartbeat_when_done(
        trace_id="trace-1", task=failing_task
    )

    with pytest.raises(expected_exception=RuntimeError):
        untracking_task()

    heartbeat_store.delete.assert_called_once_with(trace_id="trace-1")
