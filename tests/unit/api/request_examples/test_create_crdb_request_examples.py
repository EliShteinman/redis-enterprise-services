import pytest
from fastapi.openapi.models import Example
from pydantic import ValidationError

from redis_enterprise_services.api.request_examples.create_crdb_request_examples import (
    CREATE_CRDB_REQUEST_EXAMPLES,
)
from redis_enterprise_services.api.request_examples.create_database_request_examples import (
    CREATE_DATABASE_REQUEST_EXAMPLES,
)
from redis_enterprise_services.creation.requests.create_crdb_request import CreateCrdbRequest
from redis_enterprise_services.creation.requests.create_database_request import CreateDatabaseRequest


@pytest.mark.parametrize(
    argnames="example",
    argvalues=[pytest.param(example, id=name) for name, example in CREATE_CRDB_REQUEST_EXAMPLES.items()],
)
def test_every_crdb_request_example_is_a_valid_crdb_request(example: Example) -> None:
    CreateCrdbRequest.model_validate(obj=example.get("value"))


def test_a_single_site_request_is_not_a_valid_crdb_request() -> None:
    with pytest.raises(expected_exception=ValidationError):
        CreateCrdbRequest.model_validate(obj=CREATE_DATABASE_REQUEST_EXAMPLES["minimal"].get("value"))


def test_a_crdb_request_is_not_a_valid_single_site_request() -> None:
    with pytest.raises(expected_exception=ValidationError):
        CreateDatabaseRequest.model_validate(obj=CREATE_CRDB_REQUEST_EXAMPLES["minimal"].get("value"))
