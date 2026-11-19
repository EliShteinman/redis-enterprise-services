from pydantic import ValidationError


def invalid_field_paths(*, error: ValidationError) -> list[str]:
    return [".".join(str(part) for part in detail["loc"]) for detail in error.errors(include_input=False)]
