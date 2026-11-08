from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.resources.named_spec import NamedSpec


class CreationBodyBuilder[TSpec: NamedSpec](Protocol):
    def creation_body(self, *, spec: TSpec) -> dict[str, JsonValue]: ...


class SpecCreationBody[TSpec: NamedSpec](CreationBodyBuilder[TSpec]):
    def creation_body(self, *, spec: TSpec) -> dict[str, JsonValue]:
        return spec.model_dump()
