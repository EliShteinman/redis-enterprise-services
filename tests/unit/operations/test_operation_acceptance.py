from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.admission import Admission
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors


class Acceptance:
    def __init__(self) -> None:
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.store.start.return_value = None
        self.runner: MagicMock = create_autospec(spec=TaskRunner, instance=True)
        self.acceptance: OperationAcceptance = OperationAcceptance(
            store=self.store,
            runner=self.runner,
            errors=PublicErrors(
                settings=OperationSettings(public_error_codes={}, cluster_error_codes=frozenset()),
                internal_error_message="internal error",
            ),
        )

    def accept(self) -> Admission:
        return self.acceptance.accept(trace_id="trace-1", name="creating orders", task=lambda: None)


def test_an_accepted_operation_is_stored_before_it_runs() -> None:
    acceptance: Acceptance = Acceptance()
    calls: MagicMock = MagicMock()
    calls.attach_mock(mock=acceptance.store.start, attribute="start")
    calls.attach_mock(mock=acceptance.runner.submit, attribute="submit")

    acceptance.accept()

    assert [name for name, _, _ in calls.mock_calls] == ["start", "submit"]


def test_an_accepted_operation_is_stored_as_running() -> None:
    acceptance: Acceptance = Acceptance()

    acceptance.accept()

    acceptance.store.start.assert_called_once_with(operation=Operation(trace_id="trace-1"))


def test_an_operation_that_cannot_run_is_stored_as_rejected() -> None:
    acceptance: Acceptance = Acceptance()
    acceptance.runner.submit.side_effect = RuntimeError("cannot schedule new futures after shutdown")

    with pytest.raises(expected_exception=RuntimeError):
        acceptance.accept()

    last: Operation = acceptance.store.save.call_args.kwargs["operation"]
    assert (last.status, last.error and last.error.code) == (OperationStatus.REJECTED, "internal_error")


def test_an_operation_already_started_with_the_same_trace_does_not_run_again() -> None:
    acceptance: Acceptance = Acceptance()
    running: Operation = Operation(trace_id="trace-1")
    acceptance.store.start.return_value = running

    admission: Admission = acceptance.accept()

    assert (admission, acceptance.runner.submit.called) == (
        Admission(operation=running, repeated=True),
        False,
    )
