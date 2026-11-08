import logging

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.public_error import PublicError

logger: logging.Logger = logging.getLogger(name=__name__)


class PublicErrors:
    def __init__(self, *, settings: OperationSettings, internal_error_message: str) -> None:
        self._settings: OperationSettings = settings
        self._internal_error_message: str = internal_error_message

    def internal_error(self) -> PublicError:
        return PublicError(code=RedisEnterpriseServicesError.code, message=self._internal_error_message)

    def from_error(
        self, *, error: RedisEnterpriseServicesError, cluster_url: str | None = None
    ) -> PublicError:
        return self.from_code(
            error_code=error.code,
            message=error.message,
            cluster_url=cluster_url,
            cluster_error_code=error.cluster_error_code,
        )

    def from_code(
        self,
        *,
        error_code: str,
        message: str,
        cluster_url: str | None = None,
        cluster_error_code: str | None = None,
    ) -> PublicError:
        public_code: str = self.public_code(error_code=error_code)
        if public_code not in self._settings.cluster_caused_public_codes:
            return PublicError(code=public_code, message=message)
        return PublicError(
            code=public_code, message=message, cluster_url=cluster_url, cluster_error_code=cluster_error_code
        )

    def public_code(self, *, error_code: str) -> str:
        internal_code: str = RedisEnterpriseServicesError.code
        mapped_public_code: str | None = self._settings.public_code_by_error_code.get(error_code)
        if mapped_public_code is None:
            if error_code != internal_code:
                logger.warning(
                    msg=f"error {error_code} has no public code and is published as {internal_code}"
                )
            return internal_code
        if mapped_public_code != error_code:
            logger.debug(msg=f"error {error_code} is published as {mapped_public_code}")
        return mapped_public_code
