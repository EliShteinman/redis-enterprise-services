from typing import get_args

from redis_enterprise_services.api.rejection_error_code import API_ERROR_CODE_MEANINGS, ApiErrorCode


def test_every_api_error_code_has_a_meaning() -> None:
    assert set(API_ERROR_CODE_MEANINGS) == set(get_args(ApiErrorCode.__value__))
