from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.liveness.live_operations import LiveOperations
from redis_enterprise_services.operations.admission import Admission
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors

RUNNING: Operation = Operation(trace_id="trace-1")


class Acceptance:
    def __init__(self) -> None:
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.store.find.return_value = None
        self.store.start.return_value = None
        self.runner: MagicMock = create_autospec(spec=TaskRunner, instance=True)
        self.live: MagicMock = create_autospec(spec=LiveOperations, instance=True)
        self.prepare: MagicMock = MagicMock(
            return_value=PreparedRun(name="creating orders", task=lambda: None)
        )
        self.acceptance: OperationAcceptance = OperationAcceptance(
            store=self.store,
            runner=self.runner,
            live=self.live,
            errors=PublicErrors(
                settings=OperationSettings(public_error_codes={}, cluster_error_codes=frozenset()),
                internal_error_message="internal error",
            ),
        )

    def admit(self) -> Admission:
        return self.acceptance.admit(trace_id="trace-1", prepare=self.prepare)


def test_a_new_operation_is_stored_as_running_before_it_runs() -> None:
    acceptance: Acceptance = Acceptance()
    calls: MagicMock = MagicMock()
    calls.attach_mock(mock=acceptance.store.start, attribute="start")
    calls.attach_mock(mock=acceptance.runner.submit, attribute="submit")

    acceptance.admit()

    assert [(name, kwargs.get("operation")) for name, _, kwargs in calls.mock_calls] == [
        ("start", RUNNING),
        ("submit", None),
    ]


def test_a_known_trace_returns_its_operation_without_preparing() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.store.find.return_value = RUNNING

    admission: Admission = acceptance.admit()

    assert (admission, acceptance.prepare.called) == (Admission(operation=RUNNING, repeated=True), False)


def test_a_trace_started_meanwhile_does_not_run_again() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.store.start.return_value = RUNNING

    admission: Admission = acceptance.admit()

    assert (admission, acceptance.runner.submit.called) == (
        Admission(operation=RUNNING, repeated=True),
        False,
    )


def test_a_request_that_fails_its_preparation_starts_nothing() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.prepare.side_effect = InvalidNameError(message="bad name")

    with pytest.raises(expected_exception=InvalidNameError):
        acceptance.admit()

    assert not acceptance.store.start.called


def test_an_operation_that_cannot_run_is_stored_as_rejected() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        acceptance.admit()

    last: Operation = acceptance.store.save.call_args.kwargs["operation"]
    assert (last.status, last.error and last.error.code) == (OperationStatus.REJECTED, "internal_error")


def test_a_started_operation_is_kept_alive_while_it_runs() -> None:
    acceptance: Acceptance = Acceptance()

    acceptance.admit()

    acceptance.live.track.assert_called_once_with(trace_id="trace-1")


def test_a_repeated_operation_is_not_kept_alive_again() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.store.start.return_value = RUNNING

    acceptance.admit()

    assert not acceptance.live.track.called


def test_an_operation_that_cannot_run_is_no_longer_kept_alive() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        acceptance.admit()

    acceptance.live.release.assert_called_once_with(trace_id="trace-1")
