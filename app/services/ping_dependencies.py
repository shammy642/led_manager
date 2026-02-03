from __future__ import annotations

from app.services.ping_probe import PingProbe, SubprocessIcmpPingProbe


def get_ping_probe() -> PingProbe:
    return SubprocessIcmpPingProbe()
