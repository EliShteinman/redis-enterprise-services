from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.exceptions.planning import InvalidNameError
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance

REQUEST: CreationRequest = CreationRequest.model_validate(
    obj={
        "target": {
            "active_active": False,
            "sites": [{"network": "n", "site": "s", "environment": "DEV", "cluster": {"type": "generic"}}],
        },
        "body": {"database": {"name": "orders", "memory_size": 104857600}},
    }
)


def test_a_request_that_fails_the_local_checks_is_not_accepted() -> None:
    preparation: MagicMock = create_autospec(spec=CreationPreparation, instance=True)
    preparation.prepare.side_effect = InvalidNameError(message="bad name")
    acceptance: MagicMock = create_autospec(spec=OperationAcceptance, instance=True)
    creation: DatabaseCreation = DatabaseCreation(
        preparation=preparation,
        execution=create_autospec(spec=CreationExecution, instance=True),
        acceptance=acceptance,
    )

    with pytest.raises(expected_exception=InvalidNameError):
        creation.accept(trace_id="trace-1", request=REQUEST)

    assert not acceptance.accept.called
