"""Self-Defending SDN Tower - 정상 사용자 시나리오 생성기 (판단 기준 측정용).

기준표의 정상 트래픽 시나리오 5종을 실제 연결로 흘린다 (raw 패킷이 아니라 커널 TCP/UDP를 써서
SYN·FIN·RST 짝과 응답이 진짜처럼 나온다):
  1. ping            : 고정 간격 ICMP (기존 실험 0.05초)
  2. 웹 요청          : 짧은 HTTP GET, 평균 간격 web_mean초 (지수 분포)
  3. 대용량 다운로드   : download_every초마다 큰 파일 한 번
  4. DNS 조회         : 작은 UDP 질의/응답, 평균 간격 dns_mean초
  5. 정상 사용자 급증  : surge_at 시각마다 surge_workers명이 surge_seconds 동안 웹 요청 (평균 surge_think초 간격)
그리고 가끔 닫힌 포트 접속(실수)으로 RST·ICMP 도달 불가가 조금 생긴다.

표준 라이브러리만 쓴다 (Mininet 호스트의 시스템 python3로 실행).
실행 예 (Mininet 호스트 안): python3 traffic/normal_user.py --server 10.0.0.4 --duration 600
"""

from __future__ import annotations

import argparse
import random
import socket
import subprocess
import threading
import time
import urllib.request

DNS_PORT = 53
CLOSED_TCP_PORT = 8080
CLOSED_UDP_PORT = 5353


def _sleep_until(deadline: float, seconds: float, stop: threading.Event) -> bool:
    """seconds만큼 쉬되 deadline을 넘기지 않는다. 계속해도 되면 True."""
    stop.wait(max(0.0, min(seconds, deadline - time.time())))
    return not stop.is_set() and time.time() < deadline


def web_get(server: str, path: str = "/index.html") -> None:
    try:
        with urllib.request.urlopen(f"http://{server}{path}", timeout=3) as resp:
            while resp.read(65536):
                pass
    except OSError:
        pass


def dns_query(server: str, rng: random.Random) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(1.0)
        try:
            s.sendto(bytes(rng.getrandbits(8) for _ in range(40)), (server, DNS_PORT))
            s.recvfrom(512)
        except OSError:
            pass


def closed_port_mistake(server: str, rng: random.Random) -> None:
    """닫힌 포트 접속: TCP면 서버가 RST, UDP면 ICMP 도달 불가를 돌려보낸다."""
    if rng.random() < 0.5:
        try:
            socket.create_connection((server, CLOSED_TCP_PORT), timeout=1).close()
        except OSError:
            pass
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"hello", (server, CLOSED_UDP_PORT))


def run(server: str, duration: float, ping_interval: float, web_mean: float, dns_mean: float,
        download_every: float, surge_at: list, surge_seconds: float, surge_workers: int,
        mistake_every: float, seed: int, surge_think: float = 0.5) -> None:
    rng = random.Random(seed)
    start = time.time()
    deadline = start + duration
    stop = threading.Event()
    threads = []

    def loop(body, mean_gap):
        local = random.Random(rng.random())
        while _sleep_until(deadline, local.expovariate(1 / mean_gap), stop):
            body(local)

    def downloads(local=None):
        local = random.Random(rng.random())
        while _sleep_until(deadline, download_every * local.uniform(0.75, 1.25), stop):
            web_get(server, "/big.bin")

    def surge(at):
        if not _sleep_until(deadline, at, stop):
            return
        until = min(deadline, time.time() + surge_seconds)

        def worker():
            local = random.Random(rng.random())
            while time.time() < until and not stop.is_set():
                web_get(server)
                # 사람이 몰리는 상황: 각자 페이지를 보고 다음 요청 (생각 시간)
                stop.wait(local.expovariate(1 / surge_think))
        workers = [threading.Thread(target=worker, daemon=True) for _ in range(surge_workers)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

    ping = None
    if ping_interval > 0:
        ping = subprocess.Popen(["ping", "-q", "-i", str(ping_interval), "-w", str(int(duration)), server],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threads.append(threading.Thread(target=loop, args=(lambda r: web_get(server), web_mean), daemon=True))
    threads.append(threading.Thread(target=loop, args=(lambda r: dns_query(server, r), dns_mean), daemon=True))
    threads.append(threading.Thread(target=downloads, daemon=True))
    threads.append(threading.Thread(target=loop, args=(lambda r: closed_port_mistake(server, r), mistake_every),
                                    daemon=True))
    threads += [threading.Thread(target=surge, args=(at,), daemon=True) for at in surge_at]
    for t in threads:
        t.start()
    try:
        while time.time() < deadline:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    stop.set()
    if ping:
        ping.terminate()


def main() -> None:
    p = argparse.ArgumentParser(description="정상 사용자 시나리오 5종 생성기")
    p.add_argument("--server", default="10.0.0.4")
    p.add_argument("--duration", type=float, default=600)
    p.add_argument("--ping-interval", type=float, default=0.05, help="0이면 ping 없음")
    p.add_argument("--web-mean", type=float, default=1.0, help="웹 요청 평균 간격(초)")
    p.add_argument("--dns-mean", type=float, default=2.0, help="DNS 질의 평균 간격(초)")
    p.add_argument("--download-every", type=float, default=60.0, help="대용량 다운로드 간격(초)")
    p.add_argument("--surge-at", default="", help="급증 시작 시각(초) 쉼표 목록, 예: 360,480")
    p.add_argument("--surge-seconds", type=float, default=30.0)
    p.add_argument("--surge-workers", type=int, default=20)
    p.add_argument("--surge-think", type=float, default=0.5, help="급증 때 한 사람의 요청 사이 평균 간격(초)")
    p.add_argument("--mistake-every", type=float, default=45.0, help="닫힌 포트 접속 평균 간격(초)")
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()
    surge_at = [float(x) for x in a.surge_at.split(",") if x.strip()]
    run(a.server, a.duration, a.ping_interval, a.web_mean, a.dns_mean, a.download_every, surge_at,
        a.surge_seconds, a.surge_workers, a.mistake_every, a.seed, a.surge_think)


if __name__ == "__main__":
    main()
