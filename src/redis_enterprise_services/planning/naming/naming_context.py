from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.site_placement import SitePlacement


class NamingContext(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    active_active: bool
    sites: list[SitePlacement] = Field(min_length=1)
