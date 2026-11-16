from typing import get_args

from redis_enterprise_services.config.public_errors.error_kind import ErrorKind
from redis_enterprise_services.config.public_errors.public_error_code import PublicErrorCode
from redis_enterprise_services.operations.errors.public_error import (
    ERROR_KIND_MEANINGS,
    PUBLIC_ERROR_CODE_MEANINGS,
)


def test_every_public_error_code_has_a_meaning() -> None:
    assert set(PUBLIC_ERROR_CODE_MEANINGS) == set(get_args(PublicErrorCode.__value__))


def test_every_error_kind_has_a_meaning() -> None:
    assert set(ERROR_KIND_MEANINGS) == set(get_args(ErrorKind.__value__))
