from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings


class UserResourceNames:
    def __init__(self, *, settings: UserResourcesSettings) -> None:
        self._settings: UserResourcesSettings = settings

    def acl(self, *, database: str, user: str) -> str:
        return self._settings.acl_name_template.format(database=database, user=user)

    def role(self, *, database: str, user: str) -> str:
        return self._settings.role_name_template.format(database=database, user=user)
