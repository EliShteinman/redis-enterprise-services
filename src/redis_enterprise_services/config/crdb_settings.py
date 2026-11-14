from pydantic import Field, PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ApiPath, ItemPath
from redis_enterprise_services.config.wait_settings import WaitSettings


class CrdbTaskSettings(ConfigModel):
    item_path: ItemPath
    completed_status: str
    failed_statuses: frozenset[str]
    result_ttl_seconds: PositiveInt
    guid_field: str
    errors_field: str
    error_cluster_field: str
    error_code_field: str
    wait: WaitSettings


class CrdbCreationSettings(ConfigModel):
    causal_consistency: bool
    encryption: bool
    compression: int = Field(ge=0, le=6)


class CrdbSettings(ConfigModel):
    collection_path: ApiPath
    item_path: ItemPath
    list_field: str
    cluster_added_tag_fields: frozenset[str]
    creation: CrdbCreationSettings
    task: CrdbTaskSettings
