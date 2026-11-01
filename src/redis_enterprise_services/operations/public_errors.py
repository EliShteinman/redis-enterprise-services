import logging

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.error_info import ErrorInfo

logger: logging.Logger = logging.getLogger(name=__name__)


class PublicErrors:
    def __init__(self, *, settings: OperationSettings, internal_error_message: str) -> None:
        self._codes: dict[str, str] = settings.public_error_codes
        self._internal_error_message: str = internal_error_message

    def internal(self) -> ErrorInfo:
        return ErrorInfo(code=RedisEnterpriseServicesError.code, message=self._internal_error_message)

    def of(self, *, error: RedisEnterpriseServicesError) -> ErrorInfo:
        return self.info(code=error.code, message=error.message)

    def info(
        self, *, code: str, message: str, cluster: str | None = None, remote_code: str | None = None
    ) -> ErrorInfo:
        public: str = self._codes.get(code, RedisEnterpriseServicesError.code)
        if public != code:
            logger.info(msg=f"error {code} is published as {public}")
        return ErrorInfo(code=public, message=message, cluster=cluster, cluster_error_code=remote_code)
