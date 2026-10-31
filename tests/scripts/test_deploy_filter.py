import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_deployignore_exists():
    deployignore = REPO_ROOT / ".deployignore"
    assert deployignore.exists(), ".deployignore must exist in the repo root"
    content = deployignore.read_text(encoding="utf-8")
    assert "docs/" in content
    assert "tests/" in content
    assert "rules/" in content
    assert ".git/" in content


def test_model_dockerfile_has_no_rules_copy():
    dockerfile_ai = REPO_ROOT / "model" / "Dockerfile.ai"
    assert dockerfile_ai.exists()
    content = dockerfile_ai.read_text(encoding="utf-8")
    assert "COPY rules" not in content, (
        "model/Dockerfile.ai must not COPY rules because rules/ is excluded from deployment"
    )


def test_rsync_dry_run_filters_correctly():
    deployignore = REPO_ROOT / ".deployignore"
    cmd = [
        "rsync",
        "-avzn",
        f"--exclude-from={deployignore}",
        "./",
        "/tmp/deploy_test_dry_run_target/",
    ]
    res = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    output = res.stdout

    # 1. 기밀 및 비런타임 자산이 전송 목록에 포함되지 않아야 함
    assert "docs/thesis/thesis_draft.md" not in output
    assert "tests/" not in output
    assert "rules/" not in output
    assert ".git/" not in output
    assert ".venv/" not in output

    # 2. 필수 런타임 파일은 반드시 포함되어야 함
    assert "docker-compose.yml" in output
    assert "config/topology.yaml" in output
    assert "config/zones.yaml" in output
    assert "ryu/app/controller.py" in output
    assert "api/main.py" in output
    assert "model/inference_worker.py" in output
    assert "ui/Dockerfile.ui" in output
    assert "scripts/setup_large_ovs.sh" in output
    assert "scripts/deploy_remote.sh" in output
    assert "README.md" in output


def test_deploy_remote_script_executable_and_help():
    script_path = REPO_ROOT / "scripts" / "deploy_remote.sh"
    assert script_path.exists(), "scripts/deploy_remote.sh must exist"
    import os
    assert os.access(script_path, os.X_OK), "scripts/deploy_remote.sh must be executable"

    res = subprocess.run(
        [str(script_path), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "사용법" in res.stdout
    assert "--dry-run" in res.stdout


def test_deploy_remote_dry_run_execution():
    script_path = REPO_ROOT / "scripts" / "deploy_remote.sh"
    res = subprocess.run(
        [str(script_path), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "DRY-RUN" in res.stdout
    assert "docs/thesis" not in res.stdout
    assert "tests/scripts" not in res.stdout
    assert "tests/api" not in res.stdout
    assert "rules/01_environment.md" not in res.stdout
    assert "ryu/app/controller.py" in res.stdout
