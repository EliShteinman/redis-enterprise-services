from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.planning.site_target import SiteTarget


class NamingContext(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    active_active: bool
    sites: list[SiteTarget] = Field(min_length=1)
