from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.config.redis_api.crdb_settings import (
    MAX_CRDB_COMPRESSION,
    MIN_CRDB_COMPRESSION,
)


class CrdbSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    causal_consistency: bool | None = Field(
        default=None,
        description="Whether the Active-Active database keeps causal consistency between its sites. "
        "Not sent: the value configured for the environment and network.",
        examples=[False],
    )
    encryption: bool | None = Field(
        default=None,
        description="Whether the traffic between the sites of the Active-Active database is encrypted. "
        "Not sent: the value configured for the environment and network.",
        examples=[True],
    )
    compression: int | None = Field(
        default=None,
        ge=MIN_CRDB_COMPRESSION,
        le=MAX_CRDB_COMPRESSION,
        description=f"The compression level of the traffic between the sites, {MIN_CRDB_COMPRESSION} "
        f"(none) to {MAX_CRDB_COMPRESSION} (highest), "
        "one value for every site. Not sent: the value configured for the environment and network.",
        examples=[3],
    )
