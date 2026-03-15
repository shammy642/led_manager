from collections.abc import Sequence
from pathlib import Path

from app.utils.formatting import to_snake_case


class DnsmasqConfigWriter:
    def __init__(
        self,
        interface: str = "eth0",
        dhcp_range: str = "192.168.1.200,192.168.1.254,12h",
        domain: str = "box9",
        dhcp_lease_file: str | None = None,
    ) -> None:
        self.interface = interface
        self.dhcp_range = dhcp_range
        self.domain = domain
        self.dhcp_lease_file = dhcp_lease_file

    def write_config(self, devices: Sequence[dict[str, str]], output_path: Path) -> None:
        lines = [
            f"interface={self.interface}",
            f"dhcp-range={self.dhcp_range}",
            "no-resolv",
            "domain-needed",
            f"domain={self.domain}",
            "expand-hosts",
        ]
        if self.dhcp_lease_file:
            lines.append(f"dhcp-leasefile={self.dhcp_lease_file}")

        for device in devices:
            mac = device.get("mac_address", "")
            ip = device.get("ip_address", "")
            name = to_snake_case(device.get("name", ""))
            
            lines.append(f"dhcp-host={mac},{ip},{name}")

        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

