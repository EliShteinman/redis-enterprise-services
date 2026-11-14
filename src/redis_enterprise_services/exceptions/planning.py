from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class NoMatchingClusterError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "no_matching_cluster"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_CONTENT


class MixedNetworksError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "mixed_networks"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_CONTENT


class DuplicateSitesError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "duplicate_sites"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_CONTENT


class InvalidNameError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "invalid_name"
    status_code: ClassVar[int] = HTTPStatus.UNPROCESSABLE_CONTENT


class NameTakenError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "name_taken"
