from fastapi.exceptions import RequestValidationError

VALUE_ERROR_TYPE: str = "value_error"


def field_validation_error(*, location: tuple[str, str], message: str) -> RequestValidationError:
    return RequestValidationError(errors=[{"loc": location, "msg": message, "type": VALUE_ERROR_TYPE}])
