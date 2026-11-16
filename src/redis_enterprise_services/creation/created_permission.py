from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.creation.created_resources import created_resource
from redis_enterprise_services.operations.results.database_result import DatabasePermissionResult
from redis_enterprise_services.planning.planned.user_resources import UserResources
from redis_enterprise_services.planning.spec.database_spec import DatabaseUserSpec
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_permission(
    *, record: SagaRecord, user: DatabaseUserSpec, resources: UserResources
) -> DatabasePermissionResult:
    created_user: CreatedResource = created_resource(record=record, step_key=resources.user.step_key)
    created_acl: CreatedResource = created_resource(record=record, step_key=resources.acl.step_key)
    created_role: CreatedResource = created_resource(record=record, step_key=resources.role.step_key)
    return DatabasePermissionResult(
        user_uid=created_user.uid,
        user_name=created_user.name,
        user_password=user.password,
        acl_uid=created_acl.uid,
        acl_rule=NewAcl.model_validate(obj=created_acl.fields).acl,
        role_uid=created_role.uid,
        role_name=created_role.name,
    )
