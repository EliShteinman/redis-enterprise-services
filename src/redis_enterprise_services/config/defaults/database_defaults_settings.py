from enum import StrEnum

from pydantic import JsonValue

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings


class DatabaseKindDefaults(ConfigModel):
    database: dict[str, JsonValue]
    persistence_values: dict[str, dict[str, JsonValue]]
    sharding_values: dict[str, JsonValue]


class ActiveActiveDefaults(DatabaseKindDefaults):
    crdb: CrdbCreationSettings


class DatabaseKind(StrEnum):
    SINGLE_SITE = "single_site"
    ACTIVE_ACTIVE = "active_active"

    @classmethod
    def of(cls, *, active_active: bool) -> DatabaseKind:
        return cls.ACTIVE_ACTIVE if active_active else cls.SINGLE_SITE


class DatabaseDefaultsSettings(ConfigModel):
    single_site: DatabaseKindDefaults
    active_active: ActiveActiveDefaults

    def of_kind(self, *, kind: DatabaseKind) -> DatabaseKindDefaults:
        match kind:
            case DatabaseKind.SINGLE_SITE:
                return self.single_site
            case DatabaseKind.ACTIVE_ACTIVE:
                return self.active_active
