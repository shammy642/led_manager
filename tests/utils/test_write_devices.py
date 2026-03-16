from pathlib import Path
from app.utils.write_devices import DnsmasqConfigWriter

def test_dnsmasq_config_writer_default(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter()
    devices = [
        {"mac_address": "9C:05:D6:F9:24:18", "ip_address": "192.168.1.7", "name": "Box9 U6 AP!"},
        {"mac_address": "80:FA:5B:3C:F6:77", "ip_address": "192.168.1.9", "name": "box_9_laptop"},
    ]
    
    writer.write_config(devices, output_file)
    
    expected = """interface=eth0
dhcp-range=192.168.1.200,192.168.1.254,12h
no-resolv
domain-needed
domain=box9
expand-hosts
address=/box9pi.box9/192.168.1.1
dhcp-host=9C:05:D6:F9:24:18,192.168.1.7,box9_u6_ap
dhcp-host=80:FA:5B:3C:F6:77,192.168.1.9,box_9_laptop
"""
    assert output_file.read_text(encoding="utf-8") == expected

def test_dnsmasq_config_writer_custom(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter(interface="wlan0", dhcp_range="10.0.0.50,10.0.0.100,24h", domain="test", address=None)
    devices = []
    
    writer.write_config(devices, output_file)
    
    expected = """interface=wlan0
dhcp-range=10.0.0.50,10.0.0.100,24h
no-resolv
domain-needed
domain=test
expand-hosts
"""
    assert output_file.read_text(encoding="utf-8") == expected


def test_dnsmasq_config_writer_with_lease_file(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter(dhcp_lease_file="/var/lib/misc/dnsmasq.leases")
    devices = [{"mac_address": "AA:BB:CC:DD:EE:FF", "ip_address": "192.168.1.1", "name": "device"}]

    writer.write_config(devices, output_file)

    content = output_file.read_text(encoding="utf-8")
    assert "dhcp-leasefile=/var/lib/misc/dnsmasq.leases" in content


def test_dnsmasq_config_writer_no_lease_file_by_default(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter()
    writer.write_config([], output_file)

    assert "dhcp-leasefile" not in output_file.read_text(encoding="utf-8")


def test_dnsmasq_config_writer_custom_address(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter(address="/custom.host/10.0.0.1")
    writer.write_config([], output_file)

    content = output_file.read_text(encoding="utf-8")
    assert "address=/custom.host/10.0.0.1\n" in content
    assert content.count("address=") == 1


def test_dnsmasq_config_writer_no_address(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter(address=None)
    writer.write_config([], output_file)

    assert "address=" not in output_file.read_text(encoding="utf-8")
