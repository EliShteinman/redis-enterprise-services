import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.public_errors import PublicErrors

PUBLIC_ERRORS: PublicErrors = PublicErrors(
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
def test_an_error_is_published_with_its_public_code(code: str, published: str) -> None:
    assert PUBLIC_ERRORS.from_code(error_code=code, message="m").code == published


def test_only_an_error_from_a_cluster_names_the_cluster() -> None:
    published_cluster_urls: list[str | None] = [
        PUBLIC_ERRORS.from_code(
            error_code=code, message="m", cluster_url="https://c1:9443", cluster_error_code="x"
        ).cluster_url
        for code in ("cluster_rejected_request", "name_taken")
    ]

    assert published_cluster_urls == ["https://c1:9443", None]
