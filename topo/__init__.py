"""Legacy topo package.
Original implementation moved to `archive/topo/`.
"""
try:
    from archive.topo.diamond_topo import DiamondTopo, topos
except ImportError:
    pass

__all__ = ["DiamondTopo", "topos"]
