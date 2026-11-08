from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.database_spec import (
    DatabaseSpec,
    DatabaseUserSpec,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


def test_the_requested_names_are_the_database_then_each_users_acl_role_and_user() -> None:
    names: CreationNames = CreationNames(
        resource_naming=UserResourceNaming(
            settings=UserResourcesSettings(
                acl_name_template="{database}-{user}-acl",
                role_name_template="{database}-{user}-role",
                role_management="db_viewer",
            )
        )
    )
    request: DatabaseSpec = DatabaseSpec(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserSpec(name="app", password="p1", acl_rule="+@all")],
    )

    assert [(name.kind, name.name) for name in names.requested_names(spec=request)] == [
        ("database", "orders"),
        ("acl", "orders-app-acl"),
        ("role", "orders-app-role"),
        ("user", "app"),
    ]
