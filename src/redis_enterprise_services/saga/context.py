from pydantic import BaseModel

from redis_enterprise_services.exceptions.saga import MissingResultError


class SagaContext:
    def __init__(self) -> None:
        self._results: dict[str, BaseModel] = {}

    def keep(self, *, key: str, result: BaseModel) -> None:
        self._results.setdefault(key, result)

    def result_of[TResult: BaseModel](self, *, key: str, result_type: type[TResult]) -> TResult:
        result: BaseModel | None = self._results.get(key)
        if not isinstance(result, result_type):
            raise MissingResultError(message=f"step {key} has no {result_type.__name__} result")
        return result
