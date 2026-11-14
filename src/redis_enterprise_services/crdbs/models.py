from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from redis_enterprise_services.config.base_url import BaseUrl, comparable_url


class CrdbInstanceCluster(BaseModel):
    url: BaseUrl


class CrdbInstance(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    id: int
    cluster: CrdbInstanceCluster
    db_uid: str | None = None
    compression: int | None = None
    db_config: dict[str, JsonValue] = Field(default_factory=dict, repr=False)


class NamedCrdb(BaseModel):
    name: str


class Crdb(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    guid: str
    name: str
    default_db_config: dict[str, JsonValue] = Field(repr=False)
    instances: list[CrdbInstance]
    causal_consistency: bool | None = None
    encryption: bool | None = None
    featureset_version: int | None = None
    protocol_version: int | None = None

    def instance_on(self, *, api_url: str) -> CrdbInstance | None:
        wanted: str = comparable_url(url=api_url)
        return next(
            (instance for instance in self.instances if comparable_url(url=instance.cluster.url) == wanted),
            None,
        )


class CrdbInstanceChange(BaseModel):
    id: int
    db_config: dict[str, JsonValue]


class CrdbInstancesChange(BaseModel):
    instances: list[CrdbInstanceChange]


def instances_change(*, values_by_instance: dict[int, dict[str, JsonValue]]) -> CrdbInstancesChange:
    return CrdbInstancesChange(
        instances=[
            CrdbInstanceChange(id=instance_id, db_config=values)
            for instance_id, values in values_by_instance.items()
        ]
    )
