"""
Unit tests for Whitelist Safety Guardrail (Week 9).
Author: Sihyeon Park (22101489 / Tech Lead)
"""

import pytest
from harness.safety.whitelist_guard import WhitelistGuard


def test_whitelist_identifies_trunk_ports():
    guard = WhitelistGuard()
    # S1 trunks: 1, 2, 3, 4, 5
    assert guard.is_trunk_port(1, 1) is True
    assert guard.is_trunk_port(1, 2) is True
    assert guard.is_trunk_port(1, 3) is True
    assert guard.is_trunk_port(1, 4) is True
    assert guard.is_trunk_port(1, 5) is True

    # S3 trunk: 99, access: 1, 2
    assert guard.is_trunk_port(3, 99) is True
    assert guard.is_trunk_port(3, 1) is False
    assert guard.is_trunk_port(3, 2) is False


def test_whitelist_allows_access_port_isolation():
    guard = WhitelistGuard()
    # S3 P1 (h1) and P2 (h2) are access ports on user edge
    assert guard.is_access_port(3, 1) is True
    assert guard.is_access_port(3, 2) is True
    assert guard.can_isolate(3, 2) is True
    assert guard.validate_isolation_target(3, 2) is True


def test_whitelist_blocks_trunk_isolation_with_exception():
    guard = WhitelistGuard()
    # Attempting to isolate trunk port must raise ValueError
    with pytest.raises(ValueError, match="치명적 오류: DPID 1의 Port 2는 Trunk"):
        guard.validate_isolation_target(1, 2)

    with pytest.raises(ValueError, match="치명적 오류: DPID 3의 Port 99는 Trunk"):
        guard.validate_isolation_target(3, 99)


def test_whitelist_can_isolate_boolean_check():
    guard = WhitelistGuard()
    assert guard.can_isolate(1, 2) is False  # S1:P2 is trunk
    assert guard.can_isolate(3, 99) is False  # S3:P99 is trunk
    assert guard.can_isolate(5, 1) is False  # S5:P1 is h5 (Web server), protected


def test_whitelist_protected_ips():
    guard = WhitelistGuard()
    assert guard.is_ip_protected("10.0.0.11") is True
    assert guard.is_ip_protected("10.0.0.254") is True
    assert guard.is_ip_protected("10.0.0.2") is False


def test_whitelist_blocks_protected_host_port_isolation():
    """S5:1(h5 Web), S7:1(h_admin)는 트렁크가 아니라도 격리 대상이 아니다."""
    guard = WhitelistGuard()
    assert guard.can_isolate(5, 1) is False  # h5 Web
    assert guard.can_isolate(7, 1) is False  # h_admin
    assert guard.is_protected_access_port(5, 1) is True
    assert guard.is_protected_access_port(7, 1) is True
    assert guard.is_protected_access_port(3, 2) is False  # h2는 보호 대상 아님

    with pytest.raises(ValueError, match="보호 호스트 포트"):
        guard.validate_isolation_target(5, 1)
