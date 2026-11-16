from redis_enterprise_services.creation.creation_planning import CreationPlanning
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan


class SingleSiteCreationPlanning(CreationPlanning[PreparedCreation]):
    def __init__(self, *, names_check: CreationNamesCheck, planner: SingleSiteCreationPlanner) -> None:
        self._names_check: CreationNamesCheck = names_check
        self._planner: SingleSiteCreationPlanner = planner

    def plan(self, *, trace_id: str, prepared_creation: PreparedCreation) -> SagaPlan:
        return self._planner.plan(cluster=prepared_creation.cluster, spec=prepared_creation.spec)

    def ensure_names_free(self, *, prepared_creation: PreparedCreation) -> None:
        self._names_check.ensure_free(cluster=prepared_creation.cluster, spec=prepared_creation.spec)

    def fallback_cluster_url(self, *, prepared_creation: PreparedCreation) -> str:
        return prepared_creation.cluster.api_url
