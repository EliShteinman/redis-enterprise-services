from typing import Self

from pydantic import Field, PositiveInt, model_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ApiPath, ItemPath
from redis_enterprise_services.config.wait_settings import WaitSettings

MIN_CRDB_COMPRESSION: int = 0
MAX_CRDB_COMPRESSION: int = 6


class CrdbTaskSettings(ConfigModel):
    item_path: ItemPath
    id_field: str
    completed_status: str
    failed_statuses: frozenset[str] = Field(min_length=1)
    result_ttl_seconds: PositiveInt
    guid_field: str
    existing_task_error_code: str
    errors_field: str
    error_cluster_field: str
    error_code_field: str
    wait: WaitSettings

    @model_validator(mode="after")
    def reject_a_result_that_expires_during_the_wait(self) -> Self:
        if self.result_ttl_seconds <= self.wait.timeout_seconds:
            raise ValueError("result_ttl_seconds must be longer than wait.timeout_seconds")
        return self

    @model_validator(mode="after")
    def reject_a_completed_status_counted_as_failed(self) -> Self:
        if self.completed_status in self.failed_statuses:
            raise ValueError(f"{self.completed_status} cannot be both the completed and a failed status")
        return self


class CrdbCreationSettings(ConfigModel):
    causal_consistency: bool
    encryption: bool
    compression: int = Field(ge=MIN_CRDB_COMPRESSION, le=MAX_CRDB_COMPRESSION)


class CrdbSettings(ConfigModel):
    collection_path: ApiPath
    item_path: ItemPath
    list_field: str
    cluster_added_item_fields: frozenset[str]
    task: CrdbTaskSettings
