from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class CrdbInstanceCluster(BaseModel):
    url: str


class CrdbInstance(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    id: int
    cluster: CrdbInstanceCluster
    db_uid: str | None = None
    db_config: dict[str, JsonValue] = Field(default_factory=dict)


class Crdb(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    guid: str
    name: str
    default_db_config: dict[str, JsonValue]
    instances: list[CrdbInstance]

    def instance_on(self, *, api_url: str) -> CrdbInstance | None:
        return next((instance for instance in self.instances if instance.cluster.url == api_url), None)
