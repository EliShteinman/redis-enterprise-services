from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.site_placement import SitePlacement


class CreateDatabaseTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    active_active: bool = Field(
        description="Whether the database is Active-Active across several sites. All its sites must be on "
        "one network; the first site coordinates the creation.",
        examples=[False],
    )
    sites: list[SitePlacement] = Field(
        min_length=1,
        description="Where the database is created: exactly one site for a single-site database, one or more "
        "for an Active-Active one (one site gives a CRDB with a single instance).",
    )

    @model_validator(mode="after")
    def reject_several_sites_for_a_single_site_database(self) -> Self:
        if not self.active_active and len(self.sites) != 1:
            raise ValueError("a database that is not Active-Active is created on exactly one site")
        return self

    def naming_context(self) -> NamingContext:
        return NamingContext(active_active=self.active_active, sites=self.sites)


class CreateDatabaseRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    target: CreateDatabaseTarget = Field(description="Where to create the database.")
    spec: DatabaseSpec = Field(description="What to create: the database and its users.")
