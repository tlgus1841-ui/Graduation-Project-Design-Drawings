"""Legacy shim for Mininet diamond topology.

Deprecated: Mininet has been completely replaced with Native OVS (setup_native_ovs.sh) in Phase 6-A.
The original Mininet script has been archived to `archive/topo/diamond_topo.py`.
"""
try:
    from archive.topo.diamond_topo import DiamondTopo, topos
except ImportError:
    pass

__all__ = ["DiamondTopo", "topos"]
