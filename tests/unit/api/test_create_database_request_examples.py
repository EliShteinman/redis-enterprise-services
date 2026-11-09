import pytest
from fastapi.openapi.models import Example

from redis_enterprise_services.api.create_database_request_examples import CREATE_DATABASE_REQUEST_EXAMPLES
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest


@pytest.mark.parametrize(
    argnames="example",
    argvalues=[pytest.param(example, id=name) for name, example in CREATE_DATABASE_REQUEST_EXAMPLES.items()],
)
def test_every_request_example_is_a_valid_request(example: Example) -> None:
    CreateDatabaseRequest.model_validate(obj=example.get("value"))
