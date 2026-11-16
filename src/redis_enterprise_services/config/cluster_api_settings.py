from typing import Literal

from redis_enterprise_services.config.config_model import ConfigModel

type ClusterApiScheme = Literal["http", "https"]


class ClusterFieldSettings(ConfigModel):
    status: str
    error_code: str
    action_uid: str
    roles_permissions: str


class FieldsQuerySettings(ConfigModel):
    name: str
    separator: str


class ClusterApiSettings(ConfigModel):
    scheme: ClusterApiScheme
    fields: ClusterFieldSettings
    fields_query: FieldsQuerySettings
    transient_error_codes: frozenset[str]
