from typing import Protocol

from redis_enterprise_services.saga.plan.saga_plan import SagaPlan


class CreationSagaPlanning[TPrepared](Protocol):
    def plan(self, *, trace_id: str, prepared_creation: TPrepared) -> SagaPlan: ...

    def ensure_names_free(self, *, prepared_creation: TPrepared) -> None: ...

    def fallback_cluster_url(self, *, prepared_creation: TPrepared) -> str: ...
