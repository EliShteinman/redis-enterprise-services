import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.public_errors import PublicErrors

ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(public_error_codes={"cluster_error": "step_rejected"}),
    internal_error_message="internal error",
)


@pytest.mark.parametrize(
    argnames=("code", "published"),
    argvalues=[("cluster_error", "step_rejected"), ("invalid_plan", "internal_error")],
)
def test_an_error_is_published_with_its_contract_code(code: str, published: str) -> None:
    assert ERRORS.info(code=code, message="m").code == published
