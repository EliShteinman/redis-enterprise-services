from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.database_result import (
    DatabaseClusterResult,
    DatabaseResult,
    DatabaseUserResult,
)
from redis_enterprise_services.planning.database_creation_request import DatabaseUserRequest
from redis_enterprise_services.planning.single_site_creation_planner import (
    DATABASE_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_database(*, creation: PreparedCreation, record: SagaRecord) -> DatabaseResult:
    db_uid: int = created_uid(record=record, key=DATABASE_STEP_KEY)
    cluster: DatabaseClusterResult = DatabaseClusterResult(
        cluster_url=creation.cluster.api_url,
        network=creation.cluster.network,
        site=creation.cluster.site,
        environment=creation.cluster.environment,
        db_uid=db_uid,
        users=[created_user(record=record, user=user) for user in creation.request.users],
    )
    return DatabaseResult(
        name=creation.request.database.name, active_active=False, db_id=db_uid, clusters=[cluster]
    )


def created_user(*, record: SagaRecord, user: DatabaseUserRequest) -> DatabaseUserResult:
    return DatabaseUserResult(
        name=user.name,
        user_uid=created_uid(record=record, key=user_step_key(user=user)),
        role_uid=created_uid(record=record, key=role_step_key(user=user)),
        acl_uid=created_uid(record=record, key=acl_step_key(user=user)),
    )


def created_uid(*, record: SagaRecord, key: str) -> int:
    step_result: object = next(step.result for step in record.steps if step.key == key)
    return CreatedResource.model_validate(obj=step_result).uid
