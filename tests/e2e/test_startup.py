import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).parents[2]


def run_program(*, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args=[sys.executable, "-m", "redis_enterprise_services"],
        cwd=PROJECT_ROOT,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_program_starts_in_its_own_process() -> None:
    assert "redis-enterprise-services started" in run_program(environment={}).stdout


def test_invalid_configuration_exits_with_its_code() -> None:
    assert run_program(environment={"RES_LOG__LEVEL": "LOUD"}).returncode == 2


def test_invalid_configuration_is_reported_in_one_line() -> None:
    assert run_program(environment={"RES_LOG__LEVEL": "LOUD"}).stderr.strip().count("\n") == 0
