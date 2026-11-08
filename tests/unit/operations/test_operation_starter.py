from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.liveness.in_process_operation_heartbeats import InProcessOperationHeartbeats
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.start_once_result import StartOnceResult

RUNNING_OPERATION: Operation = Operation(trace_id="trace-1")


class OperationStarterHarness:
    def __init__(self) -> None:
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.store.find.return_value = None
        self.store.create_if_absent.return_value = None
        self.task_runner: MagicMock = create_autospec(spec=BackgroundTaskRunner, instance=True)
        self.operation_heartbeats: MagicMock = create_autospec(
            spec=InProcessOperationHeartbeats, instance=True
        )
        self.prepare_run: MagicMock = MagicMock(
            return_value=PreparedRun(task_name="creating orders", task=lambda: None)
        )
        self.operation_starter: OperationStarter = OperationStarter(
            store=self.store,
            task_runner=self.task_runner,
            operation_heartbeats=self.operation_heartbeats,
            public_errors=PublicErrors(
                settings=OperationSettings(
                    public_code_by_internal_code={}, public_codes_with_cluster_details=frozenset()
                ),
                internal_error_message="internal error",
            ),
        )

    def start_once(self) -> StartOnceResult:
        return self.operation_starter.start_once(trace_id="trace-1", prepare_run=self.prepare_run)


def test_a_new_operation_is_started_before_it_is_submitted() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    calls: MagicMock = MagicMock()
    calls.attach_mock(mock=harness.store.create_if_absent, attribute="create_if_absent")
    calls.attach_mock(mock=harness.task_runner.submit, attribute="submit")

    harness.start_once()

    assert [(name, kwargs.get("operation")) for name, _, kwargs in calls.mock_calls] == [
        ("create_if_absent", RUNNING_OPERATION),
        ("submit", None),
    ]


def test_a_known_trace_returns_its_operation_without_preparing() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.store.find.return_value = RUNNING_OPERATION

    result: StartOnceResult = harness.start_once()

    assert (result, harness.prepare_run.called) == (
        StartOnceResult(operation=RUNNING_OPERATION, already_existed=True),
        False,
    )


def test_an_operation_started_meanwhile_is_returned_and_not_submitted() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.store.create_if_absent.return_value = RUNNING_OPERATION

    result: StartOnceResult = harness.start_once()

    assert (result, harness.task_runner.submit.called) == (
        StartOnceResult(operation=RUNNING_OPERATION, already_existed=True),
        False,
    )


def test_a_request_that_fails_its_preparation_starts_nothing() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.prepare_run.side_effect = InvalidNameError(message="bad name")

    with pytest.raises(expected_exception=InvalidNameError):
        harness.start_once()

    assert not harness.store.create_if_absent.called


def test_a_failed_submit_stores_the_operation_as_rejected() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.task_runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        harness.start_once()

    saved_operation: Operation = harness.store.save.call_args.kwargs["operation"]
    assert (saved_operation.status, saved_operation.error and saved_operation.error.code) == (
        OperationStatus.REJECTED,
        "internal_error",
    )


def test_a_started_operation_is_tracked() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()

    harness.start_once()

    harness.operation_heartbeats.track.assert_called_once_with(trace_id="trace-1")


def test_an_operation_started_meanwhile_is_not_tracked() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.store.create_if_absent.return_value = RUNNING_OPERATION

    harness.start_once()

    assert not harness.operation_heartbeats.track.called


def test_a_failed_submit_stops_the_heartbeat() -> None:
    harness: OperationStarterHarness = OperationStarterHarness()
    harness.task_runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        harness.start_once()

    harness.operation_heartbeats.stop_heartbeat.assert_called_once_with(trace_id="trace-1")
