from redis_enterprise_services.exceptions.cluster import DuplicateResourceNameError
from redis_enterprise_services.resources.models import NamedResource


def only_one_named(*, found: list[NamedResource], name: str) -> NamedResource | None:
    if not found:
        return None
    if len(found) > 1:
        uids: list[int] = [resource.uid for resource in found]
        raise DuplicateResourceNameError(message=f"{len(found)} resources named {name}: {uids}")
    return found[0]
