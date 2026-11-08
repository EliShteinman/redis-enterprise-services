from typing import Self

from pydantic import model_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.public_error_code import PublicErrorCode


class OperationSettings(ConfigModel):
    public_code_by_internal_code: dict[str, PublicErrorCode]
    public_codes_with_cluster_details: frozenset[PublicErrorCode]

    @model_validator(mode="after")
    def reject_cluster_detail_codes_without_mapping(self) -> Self:
        public: set[str] = set(self.public_code_by_internal_code.values())
        unknown: frozenset[str] = self.public_codes_with_cluster_details - public
        if unknown:
            raise ValueError(
                f"public_codes_with_cluster_details not among the public codes: {sorted(unknown)}"
            )
        return self
