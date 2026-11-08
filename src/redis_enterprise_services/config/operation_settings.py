from typing import Self

from pydantic import model_validator

from redis_enterprise_services.config.config_model import ConfigModel


class OperationSettings(ConfigModel):
    public_error_codes: dict[str, str]
    cluster_error_codes: frozenset[str]

    @model_validator(mode="after")
    def cluster_codes_are_public_codes(self) -> Self:
        unknown: frozenset[str] = self.cluster_error_codes - set(self.public_error_codes.values())
        if unknown:
            raise ValueError(f"cluster_error_codes not among the public error codes: {sorted(unknown)}")
        return self
