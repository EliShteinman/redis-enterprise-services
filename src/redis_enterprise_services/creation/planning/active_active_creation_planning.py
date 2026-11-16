from redis_enterprise_services.creation.planning.creation_planning import CreationPlanning
from redis_enterprise_services.creation.preparation.prepared_active_active_creation import (
    PreparedActiveActiveCreation,
)
from redis_enterprise_services.planning.active_active_creation_planner import ActiveActiveCreationPlanner
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.placement.crdb_coordinator import coordinator_of
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan


class ActiveActiveCreationPlanning(CreationPlanning[PreparedActiveActiveCreation]):
    def __init__(self, *, names_check: CreationNamesCheck, planner: ActiveActiveCreationPlanner) -> None:
        self._names_check: CreationNamesCheck = names_check
        self._planner: ActiveActiveCreationPlanner = planner

    def plan(self, *, trace_id: str, prepared_creation: PreparedActiveActiveCreation) -> SagaPlan:
        return self._planner.plan(
            saga_id=trace_id, clusters=prepared_creation.clusters, spec=prepared_creation.spec
        )

    def ensure_names_free(self, *, prepared_creation: PreparedActiveActiveCreation) -> None:
        self._names_check.ensure_free_on_every_site(
            clusters=prepared_creation.clusters, spec=prepared_creation.spec
        )

    def fallback_cluster_url(self, *, prepared_creation: PreparedActiveActiveCreation) -> str:
        return coordinator_of(clusters=prepared_creation.clusters).api_url
