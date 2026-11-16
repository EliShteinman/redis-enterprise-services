from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.site_placement import SitePlacement


class CreateDatabaseTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    site: SitePlacement = Field(description="Where the database is created: the site of one cluster.")

    def naming_context(self) -> NamingContext:
        return NamingContext(site=self.site)


class CreateDatabaseRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    target: CreateDatabaseTarget = Field(description="Where to create the database.")
    spec: DatabaseSpec = Field(description="What to create: the database and its users.")
