from urllib.parse import urlsplit

from pydantic import BaseModel, Field, JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget


class CrdbClusterCredentials(BaseModel):
    username: str
    password: str = Field(repr=False)


class CrdbClusterInfo(BaseModel):
    url: str
    name: str
    credentials: CrdbClusterCredentials


class CrdbInstanceInfo(BaseModel):
    cluster: CrdbClusterInfo


class CrdbCreationBody(BaseModel):
    name: str
    default_db_config: dict[str, JsonValue]
    instances: list[CrdbInstanceInfo]


def crdb_creation_body(
    *, name: str, default_db_config: dict[str, JsonValue], members: list[ClusterTarget]
) -> CrdbCreationBody:
    return CrdbCreationBody(
        name=name,
        default_db_config=default_db_config,
        instances=[crdb_instance(target=member) for member in members],
    )


def crdb_instance(*, target: ClusterTarget) -> CrdbInstanceInfo:
    return CrdbInstanceInfo(
        cluster=CrdbClusterInfo(
            url=target.api_url,
            name=cluster_fqdn(api_url=target.api_url),
            credentials=CrdbClusterCredentials(
                username=target.credentials.username, password=target.credentials.password.get_secret_value()
            ),
        )
    )


def cluster_fqdn(*, api_url: str) -> str:
    return urlsplit(api_url).hostname or api_url
