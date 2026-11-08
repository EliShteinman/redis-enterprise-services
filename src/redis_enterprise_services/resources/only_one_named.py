from redis_enterprise_services.exceptions.cluster import DuplicateResourceNameError
from redis_enterprise_services.resources.models import CreatedResource, NamedResource


def only_one_named(*, found: list[NamedResource], name: str) -> CreatedResource | None:
    if not found:
        return None
    if len(found) > 1:
        uids: list[int] = [resource.uid for resource in found]
        raise DuplicateResourceNameError(message=f"{len(found)} resources named {name}: {uids}")
    return CreatedResource(uid=found[0].uid, name=found[0].name, action_uid=None)
