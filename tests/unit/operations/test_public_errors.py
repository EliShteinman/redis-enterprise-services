import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.public_errors import PublicErrors

ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(
        public_code_by_error_code={
            "cluster_rejected_request": "cluster_request_failed",
            "name_taken": "name_taken",
        },
        cluster_caused_public_codes=frozenset({"cluster_request_failed"}),
    ),
    internal_error_message="internal error",
)


@pytest.mark.parametrize(
    argnames=("code", "published"),
    argvalues=[("cluster_rejected_request", "cluster_request_failed"), ("invalid_plan", "internal_error")],
)
def test_an_error_is_published_with_its_contract_code(code: str, published: str) -> None:
    assert ERRORS.info(code=code, message="m").code == published


def test_only_an_error_from_a_cluster_names_the_cluster() -> None:
    published: list[str | None] = [
        ERRORS.info(code=code, message="m", cluster="https://c1:9443", cluster_error_code="x").cluster
        for code in ("cluster_rejected_request", "name_taken")
    ]

    assert published == ["https://c1:9443", None]
