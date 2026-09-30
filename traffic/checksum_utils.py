"""정상/공격 트래픽 생성기 공용 체크섬 유틸 (week05 계획서 §3.1)."""

from __future__ import annotations

from scapy.layers.inet import IP, TCP
from scapy.packet import Packet


def finalize_checksum(pkt: Packet) -> Packet:
    """전송 직전 IP/TCP Checksum을 삭제해 커널이 재계산하도록 강제한다.

    Checksum 필드를 남겨두면 Linux 커널 Checksum Offload 경로에서
    스택/OVS가 패킷을 조용히 폐기하므로 반드시 이 함수를 거쳐야 한다.
    """
    if IP in pkt:
        del pkt[IP].chksum
    if TCP in pkt:
        del pkt[TCP].chksum
    return pkt
