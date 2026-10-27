from unittest.mock import create_autospec

from pydantic import JsonValue

from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.resources.endpoint import ResourceEndpoint
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.repository import RoleRepository


def test_the_creation_body_limits_the_role_to_its_databases_by_uid_strings() -> None:
    repository: RoleRepository = RoleRepository(
        endpoint=create_autospec(spec=ResourceEndpoint, instance=True), settings=Settings().role
    )

    body: dict[str, JsonValue] = repository.creation_body(
        role=NewRole(name="db1-app-role", management="db_viewer", database_uids=[1, 7])
    )

    assert body["resources"] == [{"type": "db", "uids": ["1", "7"]}]
