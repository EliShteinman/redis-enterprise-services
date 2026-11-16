from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.placement.site_placement import SitePlacement
from redis_enterprise_services.planning.spec.active_active_spec import ActiveActiveSpec


class CreateCrdbTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    sites: list[SitePlacement] = Field(
        min_length=1,
        description="Where the Active-Active database is created: the site of one cluster per instance, "
        "all on one network. The first site coordinates the creation; one site gives a CRDB with a single "
        "instance.",
    )

    def naming_contexts(self) -> list[NamingContext]:
        return [NamingContext(site=site) for site in self.sites]


class CreateCrdbRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    target: CreateCrdbTarget = Field(description="Where to create the Active-Active database.")
    spec: ActiveActiveSpec = Field(
        description="What to create: the database, its users and the settings of the CRDB itself."
    )
