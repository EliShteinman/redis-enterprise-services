from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.planning.placement.site_placement import SitePlacement


class NamingContext(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    site: SitePlacement
