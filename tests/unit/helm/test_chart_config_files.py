import shutil
import subprocess
from base64 import b64decode
from pathlib import Path
from typing import Any

import pytest
import yaml

from redis_enterprise_services.config.config_location import CONFIG_FILE_NAMES

CHART_DIR: Path = Path(__file__).parent.parent.parent.parent / "helm"
EXAMPLE_VALUES_FILE: str = "my-values.yaml"
RELEASE: str = "release"
CLUSTERS_FILE: str = "clusters.yaml"
ENVIRONMENT_CLUSTERS_FILE: str = "prep-clusters.yaml"
ENVIRONMENT_CLUSTERS: str = "clusters:\n  prod:\n    api_port: 9443\n"
CLUSTERS_FILE_VALUE: str = "files.clusters\\.yaml"
REQUIRED_VALUES: tuple[str, ...] = (
    "image.registry",
    "route.host",
    "edge.url",
    CLUSTERS_FILE_VALUE,
    "secret.RES_STATE__URL",
    "secret.RES_STATE__KEY_PREFIX",
    "secret.ELASTIC_PASSWORD",
)

type Manifest = dict[str, Any]
type Rendering = subprocess.CompletedProcess[str]


@pytest.fixture(scope="module")
def helm() -> str:
    executable: str | None = shutil.which(cmd="helm")
    if executable is None:
        pytest.skip(reason="helm is not installed")
    return executable


@pytest.fixture(scope="module")
def chart_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    chart: Path = tmp_path_factory.mktemp(basename="chart") / "helm"
    shutil.copytree(src=CHART_DIR, dst=chart)
    (chart / "files" / ENVIRONMENT_CLUSTERS_FILE).write_text(data=ENVIRONMENT_CLUSTERS, encoding="utf-8")
    return chart


def render(*, helm: str, chart_dir: Path, overrides: tuple[str, ...]) -> Rendering:
    values_file: Path = chart_dir / EXAMPLE_VALUES_FILE
    arguments: list[str] = [helm, "template", RELEASE, str(chart_dir), "-f", str(values_file)]
    for override in overrides:
        arguments += ["--set-string", override]
    return subprocess.run(args=arguments, check=False, capture_output=True, text=True)  # noqa: S603


@pytest.fixture(scope="module")
def manifests(helm: str, chart_dir: Path) -> dict[tuple[str, str], Manifest]:
    overrides: tuple[str, ...] = (f"{CLUSTERS_FILE_VALUE}={ENVIRONMENT_CLUSTERS_FILE}",)
    rendered: Rendering = render(helm=helm, chart_dir=chart_dir, overrides=overrides)
    assert rendered.returncode == 0, rendered.stderr
    documents: list[Manifest] = [document for document in yaml.safe_load_all(rendered.stdout) if document]
    return {(document["kind"], document["metadata"]["name"]): document for document in documents}


@pytest.fixture(scope="module")
def example_values() -> Manifest:
    return yaml.safe_load(stream=(CHART_DIR / EXAMPLE_VALUES_FILE).read_text(encoding="utf-8"))


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


def environment_value(*, container: Manifest, name: str) -> str:
    return next(variable["value"] for variable in container["env"] if variable["name"] == name)


def test_the_config_map_holds_every_config_file_except_the_clusters(config_map_files: dict[str, str]) -> None:
    assert set(config_map_files) == set(CONFIG_FILE_NAMES) - {CLUSTERS_FILE}


def test_the_secret_holds_only_the_clusters_file(secret_files: dict[str, str]) -> None:
    assert set(secret_files) == {CLUSTERS_FILE}


def test_the_clusters_file_is_the_one_the_values_map_to_it(secret_files: dict[str, str]) -> None:
    assert secret_files[CLUSTERS_FILE] == ENVIRONMENT_CLUSTERS


@pytest.mark.parametrize("name", sorted(set(CONFIG_FILE_NAMES) - {CLUSTERS_FILE}))
def test_a_config_map_file_has_the_content_of_the_file_mapped_to_it(
    name: str, config_map_files: dict[str, str], example_values: Manifest
) -> None:
    mapped: Path = CHART_DIR / "files" / example_values["files"][name]
    assert config_map_files[name].strip() == mapped.read_text(encoding="utf-8").strip()


def test_the_edge_url_variable_is_the_proxy_url_of_the_values(
    service_container: Manifest, example_values: Manifest
) -> None:
    edge_url: str = environment_value(container=service_container, name="RES_EDGE__URL")
    assert edge_url == example_values["edge"]["url"]


def test_the_config_dir_variable_is_the_mount_path_of_the_config_volume(service_container: Manifest) -> None:
    mount_path: str = next(
        mount["mountPath"] for mount in service_container["volumeMounts"] if mount["name"] == "config"
    )
    assert environment_value(container=service_container, name="RES_CONFIG_DIR") == mount_path


def test_the_probes_call_the_liveness_path_of_the_shipped_config(service_container: Manifest) -> None:
    service_config: Manifest = yaml.safe_load(
        stream=(CHART_DIR / "files" / "service.yaml").read_text(encoding="utf-8")
    )
    probe_paths: set[str] = {
        service_container[probe]["httpGet"]["path"] for probe in ("livenessProbe", "readinessProbe")
    }
    assert probe_paths == {service_config["api"]["liveness_path"]}


def test_the_service_is_given_the_liveness_path_the_probes_call(service_container: Manifest) -> None:
    liveness_path: str = environment_value(container=service_container, name="RES_API__LIVENESS_PATH")
    assert liveness_path == service_container["livenessProbe"]["httpGet"]["path"]


@pytest.mark.parametrize("value", REQUIRED_VALUES)
def test_rendering_fails_without_a_required_value(value: str, helm: str, chart_dir: Path) -> None:
    rendered: Rendering = render(helm=helm, chart_dir=chart_dir, overrides=(f"{value}=",))
    assert rendered.returncode != 0
