from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.database_request import DatabaseRequest
from redis_enterprise_services.planning.site_target import SiteTarget


class CreationTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    active_active: Literal[False]
    sites: list[SiteTarget] = Field(min_length=1, max_length=1)


class CreationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    target: CreationTarget
    body: DatabaseRequest
