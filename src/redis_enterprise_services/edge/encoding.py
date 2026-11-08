import json

from pydantic import JsonValue

TEXT_ENCODING: str = "utf-8"


def encoded_json_body(*, body: JsonValue | None) -> bytes | None:
    if body is None:
        return None
    return json.dumps(obj=body).encode(TEXT_ENCODING)
