DATABASE_LOCK_SEGMENT: str = "database"
USER_LOCK_SEGMENT: str = "user"


def database_lock_key(*, cluster_url: str, database_name: str) -> str:
    return f"{cluster_url}/{DATABASE_LOCK_SEGMENT}/{database_name}"


def user_lock_key(*, cluster_url: str, user_name: str) -> str:
    return f"{cluster_url}/{USER_LOCK_SEGMENT}/{user_name}"
