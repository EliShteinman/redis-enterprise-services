from collections.abc import Callable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class StatusGoal[TRead](BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    done_status: str
    failed_statuses: frozenset[str]
    failed: Callable[[str, TRead], RedisEnterpriseServicesError]
    timed_out: Callable[[], RedisEnterpriseServicesError]
