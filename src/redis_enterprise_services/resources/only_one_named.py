from redis_enterprise_services.exceptions.cluster import DuplicateResourceNameError
from redis_enterprise_services.resources.models import NamedResource


def only_one_named[TResource: NamedResource](*, found: list[TResource], name: str) -> TResource | None:
    if not found:
        return None
    if len(found) > 1:
        uids: list[int] = [resource.uid for resource in found]
        raise DuplicateResourceNameError(message=f"{len(found)} resources named {name}: {uids}")
    return found[0]
