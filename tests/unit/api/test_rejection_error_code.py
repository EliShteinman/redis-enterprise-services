from typing import get_args

from redis_enterprise_services.api.rejection_error_code import API_ERROR_CODE_MEANINGS, ApiErrorCode
from redis_enterprise_services.config.public_error_code import PublicErrorCode
from redis_enterprise_services.config.settings import load_settings


def test_every_api_error_code_has_a_meaning() -> None:
    assert set(API_ERROR_CODE_MEANINGS) == set(get_args(ApiErrorCode.__value__))


def test_every_api_error_code_has_a_kind() -> None:
    assert set(get_args(ApiErrorCode.__value__)) <= set(load_settings().operation.error_kind_by_code)


def test_every_kind_belongs_to_a_known_code() -> None:
    known_codes: set[str] = set(get_args(ApiErrorCode.__value__)) | set(get_args(PublicErrorCode.__value__))
    assert set(load_settings().operation.error_kind_by_code) <= known_codes
