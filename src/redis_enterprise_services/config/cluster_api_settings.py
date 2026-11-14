from redis_enterprise_services.config.config_model import ConfigModel


class ClusterFieldSettings(ConfigModel):
    status: str
    error_code: str
    action_uid: str


class FieldsQuerySettings(ConfigModel):
    name: str
    separator: str


class ClusterApiSettings(ConfigModel):
    fields: ClusterFieldSettings
    fields_query: FieldsQuerySettings
    transient_error_codes: frozenset[str]
