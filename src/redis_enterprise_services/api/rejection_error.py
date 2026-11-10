from pydantic import BaseModel, Field

from redis_enterprise_services.api.rejection_error_code import API_ERROR_CODE_MEANINGS, RejectionErrorCode
from redis_enterprise_services.operations.code_meanings import code_meanings_description
from redis_enterprise_services.operations.is_none import is_none
from redis_enterprise_services.operations.public_error import PUBLIC_ERROR_CODE_DESCRIPTION

REJECTION_ERROR_CODE_DESCRIPTION: str = (
    code_meanings_description(meanings=API_ERROR_CODE_MEANINGS) + ", " + PUBLIC_ERROR_CODE_DESCRIPTION
)


class FieldError(BaseModel):
    location: str = Field(
        description="Where the problem is in the request.", examples=["body.spec.database.memory_size"]
    )
    message: str = Field(description="What is wrong there.", examples=["Field required"])


class RejectionError(BaseModel):
    code: RejectionErrorCode = Field(
        description="What kind of failure: " + REJECTION_ERROR_CODE_DESCRIPTION + ".",
        examples=["validation_error"],
    )
    message: str = Field(
        description="What went wrong, for people; not for parsing.",
        examples=["the request does not match the contract"],
    )
    details: list[FieldError] | None = Field(
        default=None,
        exclude_if=is_none,
        description="Only for validation_error: every field that does not match the contract.",
    )
