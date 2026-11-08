from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.liveness.live_operations import LiveOperations
from redis_enterprise_services.operations.acceptance_result import AcceptanceResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors

RUNNING_OPERATION: Operation = Operation(trace_id="trace-1")


class AcceptanceHarness:
    def __init__(self) -> None:
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.store.find.return_value = None
        self.store.save_if_absent.return_value = None
        self.runner: MagicMock = create_autospec(spec=BackgroundTaskRunner, instance=True)
        self.live_operations: MagicMock = create_autospec(spec=LiveOperations, instance=True)
        self.prepare: MagicMock = MagicMock(
            return_value=PreparedRun(task_name="creating orders", task=lambda: None)
        )
        self.operation_acceptance: OperationAcceptance = OperationAcceptance(
            store=self.store,
            runner=self.runner,
            live_operations=self.live_operations,
            public_errors=PublicErrors(
                settings=OperationSettings(
                    public_code_by_error_code={}, cluster_caused_public_codes=frozenset()
                ),
                internal_error_message="internal error",
            ),
        )

    def accept(self) -> AcceptanceResult:
        return self.operation_acceptance.accept(trace_id="trace-1", prepare=self.prepare)


def test_a_new_operation_is_stored_as_running_before_it_runs() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    calls: MagicMock = MagicMock()
    calls.attach_mock(mock=harness.store.save_if_absent, attribute="save_if_absent")
    calls.attach_mock(mock=harness.runner.submit, attribute="submit")

    harness.accept()

    assert [(name, kwargs.get("operation")) for name, _, kwargs in calls.mock_calls] == [
        ("save_if_absent", RUNNING_OPERATION),
        ("submit", None),
    ]


def test_a_known_trace_returns_its_operation_without_preparing() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.store.find.return_value = RUNNING_OPERATION

    acceptance: AcceptanceResult = harness.accept()

    assert (acceptance, harness.prepare.called) == (
        AcceptanceResult(operation=RUNNING_OPERATION, already_accepted=True),
        False,
    )


def test_a_trace_started_meanwhile_does_not_run_again() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.store.save_if_absent.return_value = RUNNING_OPERATION

    acceptance: AcceptanceResult = harness.accept()

    assert (acceptance, harness.runner.submit.called) == (
        AcceptanceResult(operation=RUNNING_OPERATION, already_accepted=True),
        False,
    )


def test_a_request_that_fails_its_preparation_starts_nothing() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.prepare.side_effect = InvalidNameError(message="bad name")

    with pytest.raises(expected_exception=InvalidNameError):
        harness.accept()

    assert not harness.store.save_if_absent.called


def test_an_operation_that_cannot_run_is_stored_as_rejected() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        harness.accept()

    saved_operation: Operation = harness.store.save.call_args.kwargs["operation"]
    assert (saved_operation.status, saved_operation.error and saved_operation.error.code) == (
        OperationStatus.REJECTED,
        "internal_error",
    )


def test_a_started_operation_is_tracked_while_it_runs() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()

    harness.accept()

    harness.live_operations.track.assert_called_once_with(trace_id="trace-1")


def test_an_operation_accepted_before_is_not_tracked_again() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.store.save_if_absent.return_value = RUNNING_OPERATION

    harness.accept()

    assert not harness.live_operations.track.called


def test_an_operation_that_cannot_run_is_untracked() -> None:
    harness: AcceptanceHarness = AcceptanceHarness()
    harness.runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        harness.accept()

    harness.live_operations.untrack_and_delete_heartbeat.assert_called_once_with(trace_id="trace-1")
