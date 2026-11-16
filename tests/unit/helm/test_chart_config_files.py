import shutil
import subprocess
from base64 import b64decode
from pathlib import Path
from typing import Any

import pytest
import yaml

from redis_enterprise_services.config.config_location import CONFIG_FILE_NAMES

CHART_DIR: Path = Path(__file__).parent.parent.parent.parent / "helm"
RELEASE: str = "release"
REQUIRED_VALUES: tuple[str, ...] = (
    "domain=example.com",
    "secret.RES_STATE__URL=redis://user:password@state-host:6379",
    "secret.RES_STATE__KEY_PREFIX=res:",
)
CLUSTERS_FILE: str = "clusters.yaml"

type Manifest = dict[str, Any]


@pytest.fixture(scope="module")
def manifests() -> dict[tuple[str, str], Manifest]:
    helm: str | None = shutil.which(cmd="helm")
    if helm is None:
        pytest.skip(reason="helm is not installed")
    arguments: list[str] = [helm, "template", RELEASE, str(CHART_DIR)]
    for value in REQUIRED_VALUES:
        arguments += ["--set", value]
    rendered: str = subprocess.run(args=arguments, check=True, capture_output=True, text=True).stdout  # noqa: S603
    documents: list[Manifest] = [document for document in yaml.safe_load_all(stream=rendered) if document]
    return {(document["kind"], document["metadata"]["name"]): document for document in documents}


@pytest.fixture(scope="module")
def config_map_files(manifests: dict[tuple[str, str], Manifest]) -> dict[str, str]:
    return manifests[("ConfigMap", f"{RELEASE}-redis-enterprise-services-files")]["data"]


@pytest.fixture(scope="module")
def secret_files(manifests: dict[tuple[str, str], Manifest]) -> dict[str, str]:
    encoded: dict[str, str] = manifests[("Secret", f"{RELEASE}-redis-enterprise-services-clusters")]["data"]
    return {name: b64decode(s=content).decode() for name, content in encoded.items()}


@pytest.fixture(scope="module")
def service_container(manifests: dict[tuple[str, str], Manifest]) -> Manifest:
    deployment: Manifest = manifests[("Deployment", f"{RELEASE}-redis-enterprise-services")]
    return deployment["spec"]["template"]["spec"]["containers"][0]


def test_the_config_map_holds_every_config_file_except_the_clusters(config_map_files: dict[str, str]) -> None:
    assert set(config_map_files) == set(CONFIG_FILE_NAMES) - {CLUSTERS_FILE}


def test_the_secret_holds_only_the_clusters_file(secret_files: dict[str, str]) -> None:
    assert set(secret_files) == {CLUSTERS_FILE}


@pytest.mark.parametrize("name", CONFIG_FILE_NAMES)
def test_a_mounted_file_has_the_content_of_the_chart_file(
    name: str, config_map_files: dict[str, str], secret_files: dict[str, str]
) -> None:
    mounted: dict[str, str] = config_map_files | secret_files
    assert mounted[name].strip() == (CHART_DIR / "files" / name).read_text(encoding="utf-8").strip()


def test_the_config_dir_variable_is_the_mount_path_of_the_config_volume(service_container: Manifest) -> None:
    config_dir: str = next(
        variable["value"] for variable in service_container["env"] if variable["name"] == "RES_CONFIG_DIR"
    )
    mount_path: str = next(
        mount["mountPath"] for mount in service_container["volumeMounts"] if mount["name"] == "config"
    )
    assert config_dir == mount_path
