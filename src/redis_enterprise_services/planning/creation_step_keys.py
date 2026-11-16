from redis_enterprise_services.planning.database_spec import DatabaseUserSpec

DATABASE_STEP_KEY: str = "database"
PERMISSIONS_STEP_KEY: str = "permissions"
READ_DATABASE_STEP_KEY: str = "read-database"
CRDB_STEP_KEY: str = "crdb"
LOCAL_DATABASE_STEP_KEY: str = "local-database"
READ_CRDB_STEP_KEY: str = "read-crdb"
SITE_KEY_SEPARATOR: str = "/"


def acl_step_key(*, user: DatabaseUserSpec) -> str:
    return f"acl/{user.name}"


def role_step_key(*, user: DatabaseUserSpec) -> str:
    return f"role/{user.name}"


def user_step_key(*, user: DatabaseUserSpec) -> str:
    return f"user/{user.name}"


def on_site(*, cluster_fqdn: str, step_key: str) -> str:
    return f"{cluster_fqdn}{SITE_KEY_SEPARATOR}{step_key}"
