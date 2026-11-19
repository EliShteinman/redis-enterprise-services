from redis_enterprise_services.saga.contract.saga_record import SagaRecord, StepRecord
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan


def new_saga_record(*, saga_id: str, plan: SagaPlan) -> SagaRecord:
    return SagaRecord(
        saga_id=saga_id, steps=[StepRecord(key=step.key, kind=step.kind) for step in plan.steps]
    )
