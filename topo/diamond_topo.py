"""
Self-Defending SDN Tower: 4-Switch Diamond Topology
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 4) Milestone

Topology Layout:
                  +---------------+
                  |  S2 (Primary) |
             +--->|  DPID: 2      |---+
             |    +---------------+   |
             |                        |
             | (p3: S2)               | (p2: S2)
     +---------------+          +---------------+
     |  S1 (Ingress) |          |  S4 (Egress)  |
     |  DPID: 1      |          |  DPID: 4      |
     +---------------+          +---------------+
       | (p1)   | (p2)            | (p1)
       |        |                 |
     H_legit  H_attacker        H_server
       | (p4: S3)               | (p3: S3)
       |                        |
       |    +---------------+   |
       +--->|  S3 (Bypass)  |---+
            |  DPID: 3      |
            +---------------+
"""

try:
    from mininet.topo import Topo
except ImportError:
    # Graceful fallback for non-Mininet environments (e.g., CI/test harnesses)
    class Topo(object):  # type: ignore[no-redef]
        def __init__(self, *args, **params):
            self._switches = {}
            self._hosts = {}
            self._links = []
            self.build(*args, **params)

        def build(self, *args, **params):
            pass

        def addSwitch(self, name, **opts):
            self._switches[name] = opts
            return name

        def addHost(self, name, **opts):
            self._hosts[name] = opts
            return name

        def addLink(self, node1, node2, **opts):
            self._links.append((node1, node2, opts))
            return (node1, node2)


class DiamondTopo(Topo):
    """
    4-Switch Diamond Topology with explicit port pinning.
    - S1: Ingress Switch (DPID 1)
      - Port 1: H_legit (10.0.0.1, 00:00:00:00:00:01)
      - Port 2: H_attacker (10.0.0.2, 00:00:00:00:00:02)
      - Port 3: Switch S2 (Primary trunk)
      - Port 4: Switch S3 (Bypass trunk)
    - S2: Primary Intermediate Switch (DPID 2)
      - Port 1: S1 (from S1 port 3)
      - Port 2: S4 (to S4 port 2)
    - S3: Backup Bypass Intermediate Switch (DPID 3)
      - Port 1: S1 (from S1 port 4)
      - Port 2: S4 (to S4 port 3)
    - S4: Egress Switch (DPID 4)
      - Port 1: H_server (10.0.0.4, 00:00:00:00:00:04)
      - Port 2: Switch S2 (from S2 port 2)
      - Port 3: Switch S3 (from S3 port 2)
    """

    def build(self, **_opts):
        # 1. Add Switches with explicit OpenFlow 1.3 DPIDs
        s1 = self.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")
        s3 = self.addSwitch("s3", dpid="0000000000000003", protocols="OpenFlow13")
        s4 = self.addSwitch("s4", dpid="0000000000000004", protocols="OpenFlow13")

        # 2. Add Hosts with static IP and MAC
        h_legit = self.addHost(
            "h_legit",
            ip="10.0.0.1/24",
            mac="00:00:00:00:00:01",
            defaultRoute="via 10.0.0.254",
        )
        h_attacker = self.addHost(
            "h_attacker",
            ip="10.0.0.2/24",
            mac="00:00:00:00:00:02",
            defaultRoute="via 10.0.0.254",
        )
        h_server = self.addHost(
            "h_server",
            ip="10.0.0.4/24",
            mac="00:00:00:00:00:04",
            defaultRoute="via 10.0.0.254",
        )

        # 3. Add Links with STRICT port assignments
        # S1 Access Ports:
        # S1:port 1 <-> H_legit (port 1)
        self.addLink(s1, h_legit, port1=1, port2=1)
        # S1:port 2 <-> H_attacker (port 1)
        self.addLink(s1, h_attacker, port1=2, port2=1)

        # S1 Trunk Ports:
        # S1:port 3 <-> S2:port 1 (Primary Trunk)
        self.addLink(s1, s2, port1=3, port2=1)
        # S1:port 4 <-> S3:port 1 (Bypass Trunk)
        self.addLink(s1, s3, port1=4, port2=1)

        # Intermediate to Egress Links:
        # S2:port 2 <-> S4:port 2 (Primary Trunk to Egress)
        self.addLink(s2, s4, port1=2, port2=2)
        # S3:port 2 <-> S4:port 3 (Bypass Trunk to Egress)
        self.addLink(s3, s4, port1=2, port2=3)

        # S4 Access Port:
        # S4:port 1 <-> H_server (port 1)
        self.addLink(s4, h_server, port1=1, port2=1)


# Topo dictionary for Mininet custom topology discovery
# Usage: sudo mn --custom topo/diamond_topo.py --topo diamond ...
topos = {"diamond": (lambda: DiamondTopo())}


def run():
    """Run Mininet CLI directly with RemoteController and OpenFlow13."""
    from mininet.cli import CLI
    from mininet.log import info, setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    setLogLevel("info")
    info("*** Instantiating Diamond Topology\n")
    topo = DiamondTopo()
    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=False,
        autoStaticArp=False,
    )

    info("*** Connecting to Remote SDN Controller (127.0.0.1:6653)\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )
    info(f"*** Controller {c0.name} registered\n")

    info("*** Starting Network\n")
    net.start()

    # Ensure OVS bridges are set to OpenFlow13 explicitly
    for switch in net.switches:
        switch.cmd(f"ovs-vsctl set bridge {switch.name} protocols=OpenFlow13")

    info("*** Network Ready. Entering Mininet CLI\n")
    CLI(net)

    info("*** Stopping Network\n")
    net.stop()


if __name__ == "__main__":
    run()
