from redis_enterprise_services.config.decomposition_settings import DecompositionSettings


class ResourceNames:
    def __init__(self, *, settings: DecompositionSettings) -> None:
        self._settings: DecompositionSettings = settings

    def acl(self, *, database: str, user: str) -> str:
        return self._settings.acl_name.format(database=database, user=user)

    def role(self, *, database: str, user: str) -> str:
        return self._settings.role_name.format(database=database, user=user)
