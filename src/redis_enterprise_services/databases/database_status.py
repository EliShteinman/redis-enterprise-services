from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.exceptions.cluster import DatabaseCreationFailedError


def is_active_or_raise_if_creation_failed(*, uid: int, status: str, settings: DatabaseSettings) -> bool:
    if status == settings.creation_failed_status:
        raise DatabaseCreationFailedError(message=f"database {uid} is {status}")
    return status == settings.active_status
