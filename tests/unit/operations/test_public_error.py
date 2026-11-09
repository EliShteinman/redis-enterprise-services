from typing import get_args

from redis_enterprise_services.config.public_error_code import PublicErrorCode
from redis_enterprise_services.operations.public_error import PUBLIC_ERROR_CODE_MEANINGS


def test_every_public_error_code_has_a_meaning() -> None:
    assert set(PUBLIC_ERROR_CODE_MEANINGS) == set(get_args(PublicErrorCode.__value__))
