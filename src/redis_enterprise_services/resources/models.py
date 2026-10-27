from pydantic import BaseModel

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.spec import NamedSpec


class NamedResource(BaseModel):
    uid: int
    name: str


class CreatedResource(NamedResource):
    action_uid: str | None


class CreateResourceInput[TSpec: NamedSpec](BaseModel):
    target: ClusterTarget
    spec: TSpec
