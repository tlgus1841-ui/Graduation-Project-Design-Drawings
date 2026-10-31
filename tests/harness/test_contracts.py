"""
Unit tests for SSOT contracts and segmentation configuration.
Validates:
- DefenseAction additions: QUARANTINE, RELEASE
- ZoneKind enum: USER, SERVER, ADMIN, QUARANTINE
- CountKind additions: ZONE_DENY
- ControlCommandMessage serialization/deserialization (with backward compatibility)
- config/zones.yaml parsing and validation
"""

import json
from pathlib import Path
import pytest
import yaml

from harness.contracts.sdn_events import (
    ControlCommandMessage,
    CountKind,
    DefenseAction,
    ZoneKind,
)


def test_defense_action_enums():
    assert DefenseAction.QUARANTINE.value == "QUARANTINE"
    assert DefenseAction.RELEASE.value == "RELEASE"
    assert DefenseAction.ISOLATE.value == "ISOLATE"
    assert DefenseAction.RESTORE.value == "RESTORE"


def test_zone_kind_enums():
    assert ZoneKind.USER.value == "USER"
    assert ZoneKind.SERVER.value == "SERVER"
    assert ZoneKind.ADMIN.value == "ADMIN"
    assert ZoneKind.QUARANTINE.value == "QUARANTINE"


def test_count_kind_zone_deny():
    assert CountKind.ZONE_DENY.value == "zone_deny"


def test_control_command_message_backward_compatibility():
    # Command without target_ip / target_mac (existing tests style)
    cmd = ControlCommandMessage(
        command_id="cmd-123",
        action=DefenseAction.ISOLATE.value,
        target_dpid=1,
        target_port=2,
        reason="SYN flood detected",
    )
    assert cmd.target_ip is None
    assert cmd.target_mac is None

    # Serialization roundtrip
    dumped = cmd.model_dump_json()
    loaded = ControlCommandMessage.model_validate_json(dumped)
    assert loaded.command_id == "cmd-123"
    assert loaded.action == "ISOLATE"
    assert loaded.target_ip is None


def test_control_command_message_quarantine_payload():
    # Command with target_ip / target_mac for quarantine
    cmd = ControlCommandMessage(
        command_id="quarantine-001",
        action=DefenseAction.QUARANTINE.value,
        target_dpid=1,
        target_port=2,
        reason="Lateral spread detected (SMB 445)",
        target_ip="10.0.0.2",
        target_mac="00:00:00:00:00:02",
    )
    assert cmd.target_ip == "10.0.0.2"
    assert cmd.target_mac == "00:00:00:00:00:02"

    dumped = cmd.model_dump_json()
    loaded = ControlCommandMessage.model_validate_json(dumped)
    assert loaded.action == "QUARANTINE"
    assert loaded.target_ip == "10.0.0.2"
    assert loaded.target_mac == "00:00:00:00:00:02"


def test_zones_yaml_structure():
    config_path = Path(__file__).resolve().parents[2] / "config" / "zones.yaml"
    assert config_path.exists(), f"Configuration file not found: {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # 1. Zones check
    assert "zones" in data
    assert "USER" in data["zones"]
    assert "SERVER" in data["zones"]
    assert "ADMIN" in data["zones"]
    assert "QUARANTINE" in data["zones"]
    assert "10.0.0.1" in data["zones"]["USER"]
    assert "10.0.0.11" in data["zones"]["SERVER"]
    assert "10.0.0.254" in data["zones"]["ADMIN"]
    assert "10.0.0.253" in data["zones"]["ADMIN"]

    # 2. Hosts check (8-Switch Topology)
    assert "hosts" in data
    assert "10.0.0.1" in data["hosts"]
    assert data["hosts"]["10.0.0.1"]["mac"] == "00:00:00:00:00:01"
    assert data["hosts"]["10.0.0.1"]["dpid"] == 3
    assert data["hosts"]["10.0.0.1"]["port"] == 1
    assert data["hosts"]["10.0.0.11"]["dpid"] == 5

    # 3. Rules check
    assert "rules" in data
    rule_names = [r["name"] for r in data["rules"]]
    assert "USER_TO_SERVER_WEB" in rule_names
    assert "USER_TO_SERVER_DNS" in rule_names
    assert "QUARANTINE_TO_ADMIN_HTTPS" in rule_names
    assert "QUARANTINE_TO_ADMIN_HTTP_PATCH" in rule_names

    # 4. Silent drop & lateral spread
    assert "silent_drop_udp_ports" in data
    assert 5353 in data["silent_drop_udp_ports"]  # mDNS
    assert 5355 in data["silent_drop_udp_ports"]  # LLMNR

    assert "lateral_spread_ports" in data
    assert 445 in data["lateral_spread_ports"]["tcp"]

    # 5. Hard whitelist
    assert "hard_whitelist" in data
    assert data["hard_whitelist"]["probe_ip"] == "10.0.0.240"
    assert "10.0.0.11" in data["hard_whitelist"]["protected_ips"]
    assert "10.0.0.253" in data["hard_whitelist"]["protected_ips"]
