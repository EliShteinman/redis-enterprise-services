from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings


class UserResourceNaming:
    def __init__(self, *, settings: UserResourcesSettings) -> None:
        self._settings: UserResourcesSettings = settings

    def acl_name(self, *, database_name: str, user_name: str) -> str:
        return self._settings.acl_name_template.format(database=database_name, user=user_name)

    def role_name(self, *, database_name: str, user_name: str) -> str:
        return self._settings.role_name_template.format(database=database_name, user=user_name)
