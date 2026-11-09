from redis_enterprise_services.planning.database_spec import DatabaseUserSpec

DATABASE_STEP_KEY: str = "database"
PERMISSIONS_STEP_KEY: str = "permissions"


def acl_step_key(*, user: DatabaseUserSpec) -> str:
    return f"acl/{user.name}"


def role_step_key(*, user: DatabaseUserSpec) -> str:
    return f"role/{user.name}"


def user_step_key(*, user: DatabaseUserSpec) -> str:
    return f"user/{user.name}"
