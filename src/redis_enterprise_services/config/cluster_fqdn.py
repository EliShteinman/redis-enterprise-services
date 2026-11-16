from typing import Annotated

from pydantic import Field

CLUSTER_API_SCHEME: str = "https"
PORT_SEPARATOR: str = ":"

type ClusterFqdn = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[1-9][0-9]{0,4})?$")
]


def api_url_of(*, fqdn: str, api_port: int | None) -> str:
    if PORT_SEPARATOR in fqdn:
        return f"{CLUSTER_API_SCHEME}://{fqdn}"
    if api_port is None:
        raise ValueError(
            f"cluster {fqdn} has no api_port: set it on the cluster or on a level above it, "
            "or write the port in its FQDN"
        )
    return f"{CLUSTER_API_SCHEME}://{fqdn}{PORT_SEPARATOR}{api_port}"
