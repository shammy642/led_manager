from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from ipaddress import IPv4Address

from dotenv import load_dotenv

load_dotenv(override=True)

ArpReader = Callable[[], list["ArpEntry"]]

_ARP_LINE_RE = re.compile(r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F][0-9a-fA-F:]+)")


@dataclass(frozen=True)
class ArpEntry:
    ip_address: str
    mac_address: str


def _normalize_mac(mac: str) -> str:
    return ":".join(part.zfill(2).upper() for part in mac.split(":"))


def _default_arp_reader() -> list[ArpEntry]:
    result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
    entries = []
    for line in result.stdout.splitlines():
        match = _ARP_LINE_RE.search(line)
        if match:
            ip, mac = match.group(1), match.group(2)
            entries.append(ArpEntry(ip_address=ip, mac_address=_normalize_mac(mac)))
    return entries


class ArpScanner:
    @classmethod
    def from_env(cls) -> ArpScanner | None:
        scan_subnet = os.getenv("SCAN_SUBNET")
        if not scan_subnet:
            return None
        parts = scan_subnet.split(",")
        if len(parts) < 2:
            return None
        return cls(start_ip=parts[0].strip(), end_ip=parts[1].strip())

    def __init__(
        self,
        start_ip: str,
        end_ip: str,
        *,
        arp_reader: ArpReader | None = None,
    ) -> None:
        self._start = IPv4Address(start_ip)
        self._end = IPv4Address(end_ip)
        self._arp_reader = arp_reader or _default_arp_reader

    def scan(self) -> list[ArpEntry]:
        return [
            entry
            for entry in self._arp_reader()
            if self._start <= IPv4Address(entry.ip_address) <= self._end
        ]
