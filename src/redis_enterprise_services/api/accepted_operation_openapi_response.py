from http import HTTPStatus
from typing import Any

ACCEPTED_OPERATION_OPENAPI_RESPONSE: dict[int | str, dict[str, Any]] = {
    int(HTTPStatus.ACCEPTED): {
        "description": "The command is accepted and runs in the background. Its state and result "
        "are read only from GET /v1/operations/{trace_id}. One trace id means one operation: a repeat "
        "with the same trace id (the parent id and the body are not compared) starts nothing and gets "
        "the same answer."
    }
}
