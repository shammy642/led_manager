from pathlib import Path
from app.utils.write_devices import DnsmasqConfigWriter

def test_dnsmasq_config_writer_default(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter()
    devices = [
        {"mac_address": "9C:05:D6:F9:24:18", "ip_address": "192.168.1.7", "name": "box9_u6_ap"},
        {"mac_address": "80:FA:5B:3C:F6:77", "ip_address": "192.168.1.9", "name": "box_9_laptop"},
    ]
    
    writer.write_config(devices, output_file)
    
    expected = """interface=eth0
dhcp-range=192.168.1.200,192.168.1.254,12h
no-resolv
domain-needed
domain=box9
expand-hosts
dhcp-host=9C:05:D6:F9:24:18,192.168.1.7,box9_u6_ap
dhcp-host=80:FA:5B:3C:F6:77,192.168.1.9,box_9_laptop
"""
    assert output_file.read_text(encoding="utf-8") == expected

def test_dnsmasq_config_writer_custom(tmp_path: Path):
    output_file = tmp_path / "dhcp.conf"
    writer = DnsmasqConfigWriter(interface="wlan0", dhcp_range="10.0.0.50,10.0.0.100,24h", domain="test")
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
