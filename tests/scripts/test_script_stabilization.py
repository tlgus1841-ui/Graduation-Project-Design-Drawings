import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model.criteria_engine import load_baselines  # noqa: E402


def test_native_attack_script_integrity():
    script = REPO_ROOT / "scripts" / "native_attack.sh"
    assert script.exists(), "scripts/native_attack.sh must exist"
    assert os.access(script, os.X_OK), "scripts/native_attack.sh must be executable"

    content = script.read_text(encoding="utf-8")
    assert "ns_h2" in content, "Standard 8-switch attacker namespace ns_h2 must be defined"
    assert "10.0.0.11" in content, "Standard 8-switch web server IP 10.0.0.11 must be defined"


def test_vm_demo_controller_script_integrity():
    script = REPO_ROOT / "scripts" / "vm_demo_controller.sh"
    assert script.exists(), "scripts/vm_demo_controller.sh must exist"
    assert os.access(script, os.X_OK), "scripts/vm_demo_controller.sh must be executable"

    content = script.read_text(encoding="utf-8")
    assert "sdn-tower-runtime" in content, "vm_demo_controller.sh must use sdn-tower-runtime directory"
    assert "/tmp/h1_ping.log" in content, "vm_demo_controller.sh must monitor /tmp/h1_ping.log"


def test_demo_scenario_script_integrity():
    script = REPO_ROOT / "scripts" / "demo_scenario.sh"
    assert script.exists(), "scripts/demo_scenario.sh must exist"
    assert os.access(script, os.X_OK), "scripts/demo_scenario.sh must be executable"

    content = script.read_text(encoding="utf-8")
    assert "Switch S3" in content
    assert "Switch S5" in content
    assert "Dual-Core Backbone" in content


def test_criteria_baseline_covers_all_8switch_ports():
    baseline_path = REPO_ROOT / "model" / "criteria_baseline.json"
    assert baseline_path.exists(), "model/criteria_baseline.json must exist"

    baselines = load_baselines(str(baseline_path))
    assert baselines is not None

    expected_ports = {
        (3, 1), (3, 2),  # User Zone A
        (4, 1), (4, 2),  # User Zone B
        (5, 1), (5, 2),  # Server Zone A
        (6, 1), (6, 2),  # Server Zone B
        (7, 1), (7, 2),  # Admin Zone
        (8, 1),          # Quarantine Zone
    }
    for port in expected_ports:
        assert port in baselines, f"Port {port} must be present in criteria_baseline.json"
        for ind in ("syn", "udp", "icmp", "gap", "fail"):
            assert ind in baselines[port], f"Indicator {ind} must be present for port {port}"
            mean, std = baselines[port][ind]
            assert isinstance(mean, (int, float))
            assert isinstance(std, (int, float))
