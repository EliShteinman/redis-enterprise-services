import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.exceptions.saga import InvalidPlanError
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors

PUBLIC_ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(
        public_code_by_internal_code={
            "cluster_rejected_request": "cluster_request_failed",
            "name_taken": "name_taken",
        },
        public_codes_with_cluster_details=frozenset({"cluster_request_failed"}),
        error_kind_by_code={"cluster_request_failed": "known_failure", "name_taken": "customer_fixable"},
    ),
    internal_error_message="internal error",
    unexpected_error_message="unexpected {error_type}: {error}",
)


@pytest.mark.parametrize(
    argnames=("internal_code", "public_code"),
    argvalues=[("cluster_rejected_request", "cluster_request_failed"), ("invalid_plan", "internal_error")],
)
def test_an_error_is_published_with_its_public_code(internal_code: str, public_code: str) -> None:
    assert PUBLIC_ERRORS.from_code(internal_code=internal_code, message="m").code == public_code


def test_only_a_code_configured_with_cluster_details_names_the_cluster() -> None:
    published_cluster_urls: list[str | None] = [
        PUBLIC_ERRORS.from_code(
            internal_code=internal_code, message="m", cluster_url="https://c1:9443", cluster_error_code="x"
        ).cluster_url
        for internal_code in ("cluster_rejected_request", "name_taken")
    ]

    assert published_cluster_urls == ["https://c1:9443", None]


def test_a_rejection_with_no_public_code_shows_only_the_fixed_internal_message() -> None:
    rejection: PublicError = PUBLIC_ERRORS.for_rejection(error=InvalidPlanError(message="plan details"))

    assert rejection.message == "internal error"


@pytest.mark.parametrize(
    argnames=("internal_code", "kind"),
    argvalues=[
        ("name_taken", "customer_fixable"),
        ("cluster_rejected_request", "known_failure"),
        ("invalid_plan", "needs_investigation"),
    ],
)
def test_an_error_is_published_with_the_kind_of_its_public_code(internal_code: str, kind: str) -> None:
    assert PUBLIC_ERRORS.from_code(internal_code=internal_code, message="m").kind == kind


def test_an_unexpected_error_shows_its_type_and_text() -> None:
    published: PublicError = PUBLIC_ERRORS.unexpected_error(error=KeyError("missing-key"))

    assert published.message == "unexpected KeyError: 'missing-key'"
