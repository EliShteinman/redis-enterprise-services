from pydantic import BaseModel, Field

from redis_enterprise_services.operations.public_error import PublicError


class FieldError(BaseModel):
    location: str = Field(
        description="Where the problem is in the request.", examples=["body.spec.database.memory_size"]
    )
    message: str = Field(description="What is wrong there.", examples=["Field required"])


class RejectionError(PublicError):
    details: list[FieldError] | None = Field(
        default=None,
        exclude_if=lambda details: details is None,
        description="Only for validation_error: every field that does not match the contract.",
    )
