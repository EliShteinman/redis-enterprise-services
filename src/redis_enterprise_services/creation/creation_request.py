from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.database_creation_request import DatabaseCreationRequest
from redis_enterprise_services.planning.site_placement import SitePlacement


class CreationTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    active_active: Literal[False] = Field(
        description="Whether the database is Active-Active across several sites. "
        "Only false is accepted until Active-Active is supported.",
        examples=[False],
    )
    sites: list[SitePlacement] = Field(
        min_length=1,
        max_length=1,
        description="Where the database is created. One site for a single-site database.",
    )


class CreationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    target: CreationTarget = Field(description="Where to create the database.")
    body: DatabaseCreationRequest = Field(description="What to create: the database and its users.")
