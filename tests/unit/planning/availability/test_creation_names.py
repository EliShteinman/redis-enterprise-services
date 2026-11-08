from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.database_request import DatabaseRequest, DatabaseUserRequest
from redis_enterprise_services.planning.resource_names import ResourceNames


def test_a_creation_checks_the_database_and_each_user_with_its_derived_names() -> None:
    names: CreationNames = CreationNames(
        names=ResourceNames(
            settings=UserResourcesSettings(
                acl_name_template="{database}-{user}-acl",
                role_name_template="{database}-{user}-role",
                role_management="db_viewer",
            )
        )
    )
    request: DatabaseRequest = DatabaseRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl="+@all")],
    )

    assert [(name.kind, name.name) for name in names.of(request=request)] == [
        ("database", "orders"),
        ("acl", "orders-app-acl"),
        ("role", "orders-app-role"),
        ("user", "app"),
    ]
