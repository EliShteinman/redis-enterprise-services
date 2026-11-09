from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.database_result import (
    DatabaseClusterResult,
    DatabaseResult,
    DatabaseUserResult,
)
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.single_site_creation_planner import (
    DATABASE_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.resources.created_uid import created_uid
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_database_result(*, prepared_creation: PreparedCreation, record: SagaRecord) -> DatabaseResult:
    db_uid: int = recorded_uid(record=record, step_key=DATABASE_STEP_KEY)
    cluster_result: DatabaseClusterResult = DatabaseClusterResult(
        cluster_url=prepared_creation.cluster.api_url,
        network=prepared_creation.cluster.network,
        site=prepared_creation.cluster.site,
        environment=prepared_creation.cluster.environment,
        db_uid=db_uid,
        users=[created_user_result(record=record, user=user) for user in prepared_creation.spec.users],
    )
    return DatabaseResult(
        name=prepared_creation.spec.database.name,
        active_active=False,
        db_id=db_uid,
        clusters=[cluster_result],
    )


def created_user_result(*, record: SagaRecord, user: DatabaseUserSpec) -> DatabaseUserResult:
    return DatabaseUserResult(
        name=user.name,
        user_uid=recorded_uid(record=record, step_key=user_step_key(user=user)),
        role_uid=recorded_uid(record=record, step_key=role_step_key(user=user)),
        acl_uid=recorded_uid(record=record, step_key=acl_step_key(user=user)),
    )


def recorded_uid(*, record: SagaRecord, step_key: str) -> int:
    return created_uid(step_result=record.step(key=step_key).result)
