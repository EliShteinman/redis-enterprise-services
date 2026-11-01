from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore

REQUEST: CreationRequest = CreationRequest.model_validate(
    obj={
        "target": {
            "active_active": False,
            "sites": [{"network": "n", "site": "s", "environment": "DEV", "cluster": {"type": "generic"}}],
        },
        "body": {"database": {"name": "orders", "memory_size": 104857600}},
    }
)


class Creation:
    def __init__(self) -> None:
        self.preparation: MagicMock = create_autospec(spec=CreationPreparation, instance=True)
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.runner: MagicMock = create_autospec(spec=TaskRunner, instance=True)
        self.creation: DatabaseCreation = DatabaseCreation(
            preparation=self.preparation,
            execution=create_autospec(spec=CreationExecution, instance=True),
            store=self.store,
            runner=self.runner,
        )


def test_a_request_that_fails_the_local_checks_is_neither_stored_nor_run() -> None:
    creation: Creation = Creation()
    creation.preparation.prepare.side_effect = InvalidNameError(message="bad name")

    with pytest.raises(expected_exception=InvalidNameError):
        creation.creation.accept(trace_id="trace-1", request=REQUEST)

    assert (creation.store.save.called, creation.runner.submit.called) == (False, False)


def test_an_accepted_request_is_stored_as_running_before_it_runs() -> None:
    creation: Creation = Creation()
    calls: MagicMock = MagicMock()
    calls.attach_mock(mock=creation.store.save, attribute="save")
    calls.attach_mock(mock=creation.runner.submit, attribute="submit")

    creation.creation.accept(trace_id="trace-1", request=REQUEST)

    assert [name for name, _, _ in calls.mock_calls] == ["save", "submit"]
    assert calls.mock_calls[0].kwargs["operation"] == Operation(trace_id="trace-1")
