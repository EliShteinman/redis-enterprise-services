import subprocess
import sys
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).parents[2]


def test_program_starts_in_its_own_process() -> None:
    completed: subprocess.CompletedProcess[str] = subprocess.run(
        args=[sys.executable, "-m", "redis_enterprise_services"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    assert "redis-enterprise-services started" in completed.stdout
