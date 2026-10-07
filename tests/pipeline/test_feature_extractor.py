"""feature_extractor.py 단위 검증 (week06 계획서 §5).

Redis 연동은 fakeredis로만 검증한다 — 5주차 통합 점검에서 ryu/app/controller.py가
실제 소켓 연결로 테스트를 수십~수백 초씩 블로킹시키는 문제를 확인했기 때문에,
이 모듈의 테스트는 절대 실제 redis.Redis 소켓에 연결하지 않는다.
"""

import csv

import fakeredis

from harness.contracts import REDIS_CHANNEL_PORT_STATS, PortStatsMessage
from pipeline.feature_extractor import FeatureExtractor, run, subscribe

DPID, PORT_NO = 1, 1


def _message(ts: float, rx_packets: int, rx_bytes: int, rx_errors: int = 0, duration_sec: int = 0):
    return PortStatsMessage.model_validate(
        {
            "timestamp": ts,
            "dpid": DPID,
            "stats": [
                {
                    "dpid": DPID,
                    "port_no": PORT_NO,
                    "rx_packets": rx_packets,
                    "tx_packets": 0,
                    "rx_bytes": rx_bytes,
                    "tx_bytes": 0,
                    "rx_errors": rx_errors,
                    "duration_sec": duration_sec,
                }
            ],
        }
    )


def test_first_observation_emits_no_feature():
    extractor = FeatureExtractor()
    features = extractor.update(_message(ts=0.0, rx_packets=100, rx_bytes=8000))
    assert features == []


def test_second_observation_computes_expected_deltas():
    extractor = FeatureExtractor()
    extractor.update(_message(ts=0.0, rx_packets=100, rx_bytes=8000, rx_errors=0))
    features = extractor.update(_message(ts=2.0, rx_packets=300, rx_bytes=24000, rx_errors=2, duration_sec=30))

    assert len(features) == 1
    feat = features[0]
    assert feat["dpid"] == DPID
    assert feat["port_no"] == PORT_NO
    assert feat["delta_pps"] == (300 - 100) / 2.0
    assert feat["delta_bps"] == ((24000 - 8000) / 2.0) * 8
    assert abs(feat["bpp"] - (24000 - 8000) / (300 - 100)) < 1e-6
    assert abs(feat["err_rate"] - (2 / 200)) < 1e-6
    assert feat["duration_sec"] == 30


def test_zero_packet_delta_uses_epsilon_no_zero_division():
    extractor = FeatureExtractor()
    extractor.update(_message(ts=0.0, rx_packets=100, rx_bytes=8000))
    features = extractor.update(_message(ts=2.0, rx_packets=100, rx_bytes=8000))

    assert len(features) == 1
    assert features[0]["bpp"] == 0.0
    assert features[0]["err_rate"] == 0.0


def test_counter_reset_is_skipped_and_rebaselined():
    extractor = FeatureExtractor()
    extractor.update(_message(ts=0.0, rx_packets=5000, rx_bytes=400000))
    # 스위치 재시작으로 카운터가 0 근처로 리셋된 상황
    reset_features = extractor.update(_message(ts=2.0, rx_packets=10, rx_bytes=800))
    assert reset_features == []

    # 리셋 이후부터는 정상적으로 델타가 계산되어야 한다
    next_features = extractor.update(_message(ts=4.0, rx_packets=210, rx_bytes=16800))
    assert len(next_features) == 1
    assert next_features[0]["delta_pps"] == (210 - 10) / 2.0


def test_duplicate_timestamp_is_skipped():
    extractor = FeatureExtractor()
    extractor.update(_message(ts=5.0, rx_packets=100, rx_bytes=8000))
    features = extractor.update(_message(ts=5.0, rx_packets=200, rx_bytes=16000))
    assert features == []


def _port_stat(port_no: int, rx_packets: int, rx_bytes: int, duration_sec: int = 0):
    return {
        "dpid": 1, "port_no": port_no,
        "rx_packets": rx_packets, "tx_packets": 0,
        "rx_bytes": rx_bytes, "tx_bytes": 0,
        "duration_sec": duration_sec,
    }


def test_multiple_ports_tracked_independently():
    extractor = FeatureExtractor()
    msg1 = PortStatsMessage.model_validate({
        "timestamp": 0.0, "dpid": 1,
        "stats": [_port_stat(1, 0, 0), _port_stat(2, 0, 0)],
    })
    msg2 = PortStatsMessage.model_validate({
        "timestamp": 1.0, "dpid": 1,
        "stats": [
            _port_stat(1, rx_packets=100, rx_bytes=8000, duration_sec=1),
            _port_stat(2, rx_packets=5000, rx_bytes=320000, duration_sec=1),
        ],
    })
    extractor.update(msg1)
    features = extractor.update(msg2)

    by_port = {f["port_no"]: f for f in features}
    assert by_port[1]["delta_pps"] == 100.0
    assert by_port[2]["delta_pps"] == 5000.0


def test_run_consumes_fakeredis_messages_and_logs_csv(tmp_path):
    client = fakeredis.FakeRedis()
    pubsub = subscribe(client)

    msg1 = _message(ts=0.0, rx_packets=100, rx_bytes=8000)
    msg2 = _message(ts=2.0, rx_packets=5100, rx_bytes=326400)  # SYN Flood 유사 BPP 급감 구간

    client.publish(REDIS_CHANNEL_PORT_STATS, msg1.model_dump_json())
    client.publish(REDIS_CHANNEL_PORT_STATS, msg2.model_dump_json())

    out = tmp_path / "traffic_data.csv"
    written = run(pubsub, str(out), label=1, max_messages=2, poll_timeout=0.1)

    assert written == 1  # 첫 메시지는 기준점이라 피처 없음, 두 번째만 기록
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["label"] == "1"
    assert float(rows[0]["bpp"]) < 70  # 공격성 소형 패킷 특성 반영 확인


def test_run_skips_corrupted_payload(tmp_path):
    client = fakeredis.FakeRedis()
    pubsub = subscribe(client)

    client.publish(REDIS_CHANNEL_PORT_STATS, "{not valid json,")
    client.publish(REDIS_CHANNEL_PORT_STATS, _message(ts=0.0, rx_packets=1, rx_bytes=1).model_dump_json())

    out = tmp_path / "traffic_data.csv"
    written = run(pubsub, str(out), label=0, max_messages=2, poll_timeout=0.1)

    assert written == 0  # 손상 메시지 스킵 + 두 번째는 최초 관측치라 피처 없음
    assert not out.exists() or out.read_text(encoding="utf-8") == ""
