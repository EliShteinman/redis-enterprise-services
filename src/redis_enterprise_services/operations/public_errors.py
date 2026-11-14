import logging

from redis_enterprise_services.config.error_kind import UNKNOWN_ERROR_KIND, ErrorKind
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.public_error_code import PublicErrorCode
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.public_error import PublicError

logger: logging.Logger = logging.getLogger(name=__name__)

INTERNAL_ERROR_CODE: PublicErrorCode = "internal_error"


class PublicErrors:
    def __init__(
        self, *, settings: OperationSettings, internal_error_message: str, unexpected_error_message: str
    ) -> None:
        self._settings: OperationSettings = settings
        self._internal_error_message: str = internal_error_message
        self._unexpected_error_message: str = unexpected_error_message

    def internal_error(self) -> PublicError:
        return self._internal_error_with(message=self._internal_error_message)

    def unexpected_error(self, *, error: BaseException) -> PublicError:
        return self._internal_error_with(
            message=self._unexpected_error_message.format(error_type=type(error).__name__, error=error)
        )

    def from_error(
        self, *, error: RedisEnterpriseServicesError, cluster_url: str | None = None
    ) -> PublicError:
        return self.from_code(
            internal_code=error.code,
            message=error.message,
            cluster_url=cluster_url,
            cluster_error_code=error.cluster_error_code,
        )

    def for_rejection(
        self, *, error: RedisEnterpriseServicesError, cluster_url: str | None = None
    ) -> PublicError:
        published: PublicError = self.from_error(error=error, cluster_url=cluster_url)
        if published.code == INTERNAL_ERROR_CODE:
            return self.internal_error()
        return published

    def from_code(
        self,
        *,
        internal_code: str,
        message: str,
        cluster_url: str | None = None,
        cluster_error_code: str | None = None,
    ) -> PublicError:
        public_code: PublicErrorCode = self.public_code(internal_code=internal_code)
        kind: ErrorKind = self.kind_of(code=public_code)
        if not self._shows_cluster_details(public_code=public_code):
            return PublicError(code=public_code, kind=kind, message=message)
        return PublicError(
            code=public_code,
            kind=kind,
            message=message,
            cluster_url=cluster_url,
            cluster_error_code=cluster_error_code,
        )

    def public_code(self, *, internal_code: str) -> PublicErrorCode:
        mapped_public_code: PublicErrorCode | None = self._settings.public_code_by_internal_code.get(
            internal_code
        )
        if mapped_public_code is None:
            if internal_code != INTERNAL_ERROR_CODE:
                logger.warning(
                    msg=f"error {internal_code} has no public code and is published as {INTERNAL_ERROR_CODE}"
                )
            return INTERNAL_ERROR_CODE
        if mapped_public_code != internal_code:
            logger.debug(msg=f"error {internal_code} is published as {mapped_public_code}")
        return mapped_public_code

    def kind_of(self, *, code: str) -> ErrorKind:
        kind: ErrorKind | None = self._settings.error_kind_by_code.get(code)
        if kind is None:
            logger.warning(msg=f"error code {code} has no kind and is published as {UNKNOWN_ERROR_KIND}")
            return UNKNOWN_ERROR_KIND
        return kind

    def _internal_error_with(self, *, message: str) -> PublicError:
        return PublicError(
            code=INTERNAL_ERROR_CODE, kind=self.kind_of(code=INTERNAL_ERROR_CODE), message=message
        )

    def _shows_cluster_details(self, *, public_code: PublicErrorCode) -> bool:
        return public_code in self._settings.public_codes_with_cluster_details
