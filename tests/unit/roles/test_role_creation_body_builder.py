from pydantic import JsonValue

from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.role_creation_body_builder import RoleCreationBodyBuilder


def test_the_creation_body_limits_the_role_to_its_databases_by_uid_strings() -> None:
    body: dict[str, JsonValue] = RoleCreationBodyBuilder(settings=load_settings().role).creation_body(
        spec=NewRole(name="db1-app-role", management="db_viewer", database_uids=[1, 7])
    )

    assert body["resources"] == [{"type": "db", "uids": ["1", "7"]}]
