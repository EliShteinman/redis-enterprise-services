from typing import Self, get_args

from pydantic import model_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.error_kind import ErrorKind
from redis_enterprise_services.config.public_error_code import PublicErrorCode


class OperationSettings(ConfigModel):
    public_code_by_internal_code: dict[str, PublicErrorCode]
    public_codes_with_cluster_details: frozenset[PublicErrorCode]
    error_kind_by_code: dict[str, ErrorKind]

    @model_validator(mode="after")
    def reject_cluster_detail_codes_without_mapping(self) -> Self:
        public: set[str] = set(self.public_code_by_internal_code.values())
        unknown: frozenset[str] = self.public_codes_with_cluster_details - public
        if unknown:
            raise ValueError(
                f"public_codes_with_cluster_details not among the public codes: {sorted(unknown)}"
            )
        return self

    @model_validator(mode="after")
    def reject_public_codes_without_kind(self) -> Self:
        without_kind: set[str] = set(get_args(PublicErrorCode.__value__)) - set(self.error_kind_by_code)
        if without_kind:
            raise ValueError(f"error_kind_by_code has no kind for the public codes {sorted(without_kind)}")
        return self
