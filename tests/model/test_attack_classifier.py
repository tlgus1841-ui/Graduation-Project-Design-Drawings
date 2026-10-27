"""attack_classifier.py 단위 검증 (DDoS 외 공격 유형: Port Scan, Slow Drift)."""

from harness.contracts import ThreatType
from model.attack_classifier import (
    CATEGORY_TO_THREAT_TYPE,
    AttackCategory,
    SecondaryAttackClassifier,
    StreakGuard,
)


def _feature(err_rate=0.0, delta_pps=50.0, bpp=800.0, dpid=1, port_no=2):
    return {"dpid": dpid, "port_no": port_no, "delta_pps": delta_pps, "delta_bps": delta_pps * bpp,
            "bpp": bpp, "err_rate": err_rate, "duration_sec": 30}


class TestStreakGuard:
    def test_confirms_after_consecutive_true(self):
        guard = StreakGuard(consecutive_required=2)
        assert guard.observe(True) is False
        assert guard.observe(True) is True

    def test_single_blip_does_not_confirm(self):
        guard = StreakGuard(consecutive_required=2)
        assert guard.observe(True) is False
        assert guard.observe(False) is False
        assert guard.observe(True) is False  # streak restarted


class TestSecondaryAttackClassifierPortScan:
    def test_high_err_rate_is_classified_as_port_scan(self):
        clf = SecondaryAttackClassifier()
        clf.observe(_feature(err_rate=0.0))  # baseline
        cat1, confirmed1 = clf.observe(_feature(err_rate=0.5))
        cat2, confirmed2 = clf.observe(_feature(err_rate=0.6))
        assert cat1 == AttackCategory.PORT_SCAN and confirmed1 is False
        assert cat2 == AttackCategory.PORT_SCAN and confirmed2 is True

    def test_normal_traffic_never_confirms_port_scan(self):
        clf = SecondaryAttackClassifier()
        for _ in range(10):
            category, confirmed = clf.observe(_feature(err_rate=0.0))
            assert confirmed is False

    def test_single_error_spike_resets_and_does_not_confirm(self):
        clf = SecondaryAttackClassifier()
        clf.observe(_feature(err_rate=0.0))
        clf.observe(_feature(err_rate=0.5))  # 1st suspicious sample
        clf.observe(_feature(err_rate=0.0))  # back to normal, streak resets
        cat, confirmed = clf.observe(_feature(err_rate=0.5))  # 1st again, not 2nd
        assert confirmed is False


class TestSecondaryAttackClassifierSlowDrift:
    def test_gradual_duration_drift_eventually_confirms_slow_drift(self):
        clf = SecondaryAttackClassifier(ewma_feature="duration_sec", ewma_alpha=0.2, ewma_k=2.0)
        confirmed_at = None
        duration = 30.0
        for step in range(60):
            feature = _feature(err_rate=0.0)
            feature["duration_sec"] = duration
            category, confirmed = clf.observe(feature)
            if confirmed and confirmed_at is None:
                confirmed_at = step
                assert category == AttackCategory.SLOW_DRIFT
            duration += 5.0  # 서서히 증가하는 연결 지속시간 (Slowloris류 프록시 신호)
        assert confirmed_at is not None


class TestCategoryThreatTypeMapping:
    def test_every_category_except_normal_maps_to_a_contract_threat_type(self):
        for category in AttackCategory:
            if category == AttackCategory.NORMAL:
                continue
            assert category in CATEGORY_TO_THREAT_TYPE
            # SSOT 계약(harness.contracts.ThreatType)의 실제 값과 일치해야 한다.
            assert CATEGORY_TO_THREAT_TYPE[category] in {t.value for t in ThreatType}

    def test_port_scan_and_slow_ddos_are_distinct_from_volumetric_flood(self):
        assert CATEGORY_TO_THREAT_TYPE[AttackCategory.PORT_SCAN] == ThreatType.PORT_SCAN.value
        assert CATEGORY_TO_THREAT_TYPE[AttackCategory.SLOW_DRIFT] == ThreatType.SLOW_DDOS.value
        assert CATEGORY_TO_THREAT_TYPE[AttackCategory.VOLUMETRIC_FLOOD] == ThreatType.SYN_FLOOD_SPOOFING.value
