import logging

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.error_info import ErrorInfo

logger: logging.Logger = logging.getLogger(name=__name__)


class PublicErrors:
    def __init__(self, *, settings: OperationSettings, internal_error_message: str) -> None:
        self._settings: OperationSettings = settings
        self._internal_error_message: str = internal_error_message

    def internal_error(self) -> ErrorInfo:
        return ErrorInfo(code=RedisEnterpriseServicesError.code, message=self._internal_error_message)

    def from_error(self, *, error: RedisEnterpriseServicesError, cluster_url: str | None = None) -> ErrorInfo:
        return self.from_code(
            code=error.code,
            message=error.message,
            cluster_url=cluster_url,
            cluster_error_code=error.cluster_error_code,
        )

    def from_code(
        self,
        *,
        code: str,
        message: str,
        cluster_url: str | None = None,
        cluster_error_code: str | None = None,
    ) -> ErrorInfo:
        public_code: str = self.public_code(code=code)
        if public_code not in self._settings.cluster_caused_public_codes:
            return ErrorInfo(code=public_code, message=message)
        return ErrorInfo(
            code=public_code, message=message, cluster_url=cluster_url, cluster_error_code=cluster_error_code
        )

    def public_code(self, *, code: str) -> str:
        internal_code: str = RedisEnterpriseServicesError.code
        public_code_or_none: str | None = self._settings.public_code_by_error_code.get(code)
        if public_code_or_none is None:
            if code != internal_code:
                logger.warning(msg=f"error {code} has no public code and is published as {internal_code}")
            return internal_code
        if public_code_or_none != code:
            logger.debug(msg=f"error {code} is published as {public_code_or_none}")
        return public_code_or_none
