from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.resources.named_spec import NamedSpec


class NamedResource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    uid: int
    name: str


class ClusterObject(NamedResource):
    fields: dict[str, JsonValue]


class CreatedResource(ClusterObject):
    action_uid: str | None


class DeletionStarted(BaseModel):
    action_uid: str | None
    fields: dict[str, JsonValue]


class CreateResourceInput[TSpec: NamedSpec](BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    spec: TSpec
