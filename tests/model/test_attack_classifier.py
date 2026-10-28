"""attack_classifier.py 단위 검증 (DDoS 외 공격 유형: Port Scan, Slow Drift).

v2: err_rate(rx_errors)/duration_sec 기반 판정을 delta_pps EWMA + 작은 BPP +
플러드 임계치 미달 기반으로 교체했다 (실제 OVS 트래픽에서 작동 가능한 신호).
"""

from harness.contracts import ThreatType
from model.attack_classifier import (
    CATEGORY_TO_THREAT_TYPE,
    AttackCategory,
    SecondaryAttackClassifier,
    StreakGuard,
)


def _feature(delta_pps=20.0, bpp=800.0, dpid=1, port_no=2, err_rate=0.0):
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

    def test_streak_property_tracks_current_run_length(self):
        guard = StreakGuard(consecutive_required=2)
        guard.observe(True)
        guard.observe(True)
        guard.observe(True)
        assert guard.streak == 3
        guard.observe(False)
        assert guard.streak == 0


class TestSecondaryAttackClassifierPortScan:
    def test_small_packet_burst_below_flood_threshold_is_confirmed_as_port_scan(self):
        clf = SecondaryAttackClassifier(sub_flood_pps=100.0)
        # 조용한 기준선으로 EWMA 베이스라인을 쌓는다 (warmup 통과).
        for _ in range(6):
            clf.observe(_feature(delta_pps=5.0, bpp=60.0))
        # 플러드 임계치(100)에는 한참 못 미치지만 베이스라인 대비 튀는 소형 패킷 버스트.
        cat1, confirmed1 = clf.observe(_feature(delta_pps=80.0, bpp=60.0))
        cat2, confirmed2 = clf.observe(_feature(delta_pps=80.0, bpp=60.0))
        assert cat1 == AttackCategory.PORT_SCAN and confirmed1 is False
        assert cat2 == AttackCategory.PORT_SCAN and confirmed2 is True

    def test_normal_steady_traffic_never_confirms_anything(self):
        clf = SecondaryAttackClassifier()
        for _ in range(20):
            category, confirmed = clf.observe(_feature(delta_pps=20.0, bpp=800.0))
            assert confirmed is False
            assert category == AttackCategory.NORMAL

    def test_large_packets_never_classified_as_port_scan_even_if_pps_jumps(self):
        """BPP가 크면(정상적인 대용량 트래픽) 플러드 임계치 미달이라도 공격으로 보지 않는다."""
        clf = SecondaryAttackClassifier(sub_flood_pps=100.0)
        for _ in range(6):
            clf.observe(_feature(delta_pps=5.0, bpp=800.0))
        for _ in range(5):
            category, confirmed = clf.observe(_feature(delta_pps=80.0, bpp=800.0))
            assert confirmed is False

    def test_single_burst_tick_resets_and_does_not_confirm(self):
        clf = SecondaryAttackClassifier(sub_flood_pps=100.0)
        for _ in range(6):
            clf.observe(_feature(delta_pps=5.0, bpp=60.0))
        clf.observe(_feature(delta_pps=80.0, bpp=60.0))  # 1st suspicious sample
        clf.observe(_feature(delta_pps=5.0, bpp=60.0))  # back to baseline, streak resets
        cat, confirmed = clf.observe(_feature(delta_pps=80.0, bpp=60.0))  # 1st again, not 2nd
        assert confirmed is False


class TestSecondaryAttackClassifierSlowDrift:
    def test_sustained_small_packet_anomaly_escalates_to_slow_drift(self):
        clf = SecondaryAttackClassifier(sub_flood_pps=100.0, sustained_ticks_for_slow=10)
        for _ in range(6):
            clf.observe(_feature(delta_pps=5.0, bpp=60.0))

        categories = []
        for _ in range(15):
            category, confirmed = clf.observe(_feature(delta_pps=80.0, bpp=60.0))
            if confirmed:
                categories.append(category)

        assert AttackCategory.PORT_SCAN in categories  # 처음엔 짧은 버스트로 분류
        assert categories[-1] == AttackCategory.SLOW_DRIFT  # 오래 계속되니 승격


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
