from collections.abc import Callable
from typing import Final

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class StatusGoal[TRead]:
    def __init__(
        self,
        *,
        done_status: str,
        failed_statuses: frozenset[str],
        failed: Callable[[str, TRead], RedisEnterpriseServicesError],
        timed_out: Callable[[], RedisEnterpriseServicesError],
    ) -> None:
        self.done_status: Final[str] = done_status
        self.failed_statuses: Final[frozenset[str]] = failed_statuses
        self.failed: Final[Callable[[str, TRead], RedisEnterpriseServicesError]] = failed
        self.timed_out: Final[Callable[[], RedisEnterpriseServicesError]] = timed_out
