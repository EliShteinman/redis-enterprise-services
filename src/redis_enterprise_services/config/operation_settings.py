from typing import Self

from pydantic import model_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.public_error_code import PublicErrorCode


class OperationSettings(ConfigModel):
    public_code_by_error_code: dict[str, PublicErrorCode]
    cluster_caused_public_codes: frozenset[PublicErrorCode]

    @model_validator(mode="after")
    def cluster_caused_codes_are_public_codes(self) -> Self:
        public: set[str] = set(self.public_code_by_error_code.values())
        unknown: frozenset[str] = self.cluster_caused_public_codes - public
        if unknown:
            raise ValueError(f"cluster_caused_public_codes not among the public codes: {sorted(unknown)}")
        return self
