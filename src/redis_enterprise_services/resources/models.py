from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.resources.spec import NamedSpec


class NamedResource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(hide_input_in_errors=True)

    uid: int
    name: str


class CreatedResource(NamedResource):
    action_uid: str | None


class CreateResourceInput[TSpec: NamedSpec](BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    spec: TSpec
