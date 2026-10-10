"""
Unit tests for Whitelist Safety Guardrail (Week 9).
Author: Sihyeon Park (22101489 / Tech Lead)
"""

import pytest
from harness.safety.whitelist_guard import WhitelistGuard


def test_whitelist_identifies_trunk_ports():
    guard = WhitelistGuard()
    # S1 trunks: 3, 4
    assert guard.is_trunk_port(1, 3) is True
    assert guard.is_trunk_port(1, 4) is True
    assert guard.is_trunk_port(1, 1) is False
    assert guard.is_trunk_port(1, 2) is False

    # S2 trunks: 1, 2
    assert guard.is_trunk_port(2, 1) is True
    assert guard.is_trunk_port(2, 2) is True


def test_whitelist_allows_access_port_isolation():
    guard = WhitelistGuard()
    # S1 P1 (H_legit), P2 (H_attacker)
    assert guard.can_isolate(1, 1) is True
    assert guard.can_isolate(1, 2) is True
    assert guard.validate_isolation_target(1, 2) is True


def test_whitelist_blocks_trunk_isolation_with_exception():
    guard = WhitelistGuard()
    # Attempting to isolate trunk port must raise ValueError
    with pytest.raises(ValueError, match="치명적 오류: DPID 1의 Port 3는 Trunk"):
        guard.validate_isolation_target(1, 3)

    with pytest.raises(ValueError, match="치명적 오류: DPID 2의 Port 1는 Trunk"):
        guard.validate_isolation_target(2, 1)


def test_whitelist_can_isolate_boolean_check():
    guard = WhitelistGuard()
    assert guard.can_isolate(1, 3) is False
    assert guard.can_isolate(2, 2) is False
    assert guard.can_isolate(4, 1) is True  # S4:P1 is H_server access port


def test_whitelist_protected_ips():
    guard = WhitelistGuard()
    assert guard.is_ip_protected("10.0.0.1") is True
    assert guard.is_ip_protected("10.0.0.4") is True
    assert guard.is_ip_protected("10.0.0.2") is False
