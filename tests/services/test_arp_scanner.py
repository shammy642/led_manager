import subprocess
from unittest.mock import MagicMock

import pytest

from app.services.arp_scanner import ArpEntry, ArpScanner, _default_arp_reader, _normalize_mac


def _make_reader(*entries: ArpEntry):
    def reader() -> list[ArpEntry]:
        return list(entries)

    return reader


class TestNormalizeMac:
    def test_uppercases_mac(self):
        assert _normalize_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    def test_zero_pads_single_digit_groups(self):
        assert _normalize_mac("0:1:2:3:4:5") == "00:01:02:03:04:05"

    def test_already_normalized_unchanged(self):
        assert _normalize_mac("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"


class TestDefaultArpReader:
    def test_parses_macos_style_arp_output(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = (
            "? (192.168.1.1) at aa:bb:cc:dd:ee:ff on en0 ifscope [ethernet]\n"
            "router.local (192.168.1.2) at 11:22:33:44:55:66 on en0 [ethernet]\n"
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        entries = _default_arp_reader()
        assert len(entries) == 2
        assert entries[0] == ArpEntry(ip_address="192.168.1.1", mac_address="AA:BB:CC:DD:EE:FF")
        assert entries[1] == ArpEntry(ip_address="192.168.1.2", mac_address="11:22:33:44:55:66")

    def test_skips_incomplete_entries(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = (
            "? (192.168.1.1) at (incomplete) on en0\n"
            "? (192.168.1.2) at <incomplete>  eth0\n"
            "? (192.168.1.3) at aa:bb:cc:dd:ee:ff on en0\n"
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        entries = _default_arp_reader()
        assert len(entries) == 1
        assert entries[0].ip_address == "192.168.1.3"

    def test_returns_empty_list_on_no_output(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = ""
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        assert _default_arp_reader() == []

    def test_zero_pads_short_mac_groups(self, monkeypatch):
        mock_result = MagicMock()
        mock_result.stdout = "? (10.0.0.1) at 0:c:29:3a:4b:5c on eth0\n"
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_result)
        entries = _default_arp_reader()
        assert entries[0].mac_address == "00:0C:29:3A:4B:5C"


class TestArpScannerFromEnv:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("SCAN_SUBNET", raising=False)
        assert ArpScanner.from_env() is None

    def test_returns_none_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("SCAN_SUBNET", "")
        assert ArpScanner.from_env() is None

    def test_returns_none_when_only_one_part(self, monkeypatch):
        monkeypatch.setenv("SCAN_SUBNET", "192.168.1.200")
        assert ArpScanner.from_env() is None

    def test_parses_start_and_end_from_dnsmasq_format(self, monkeypatch):
        monkeypatch.setenv("SCAN_SUBNET", "192.168.1.200,192.168.1.254,12h")
        scanner = ArpScanner.from_env()
        assert scanner is not None
        assert str(scanner._start) == "192.168.1.200"
        assert str(scanner._end) == "192.168.1.254"

    def test_parses_format_without_lease_time(self, monkeypatch):
        monkeypatch.setenv("SCAN_SUBNET", "10.0.0.1,10.0.0.100")
        scanner = ArpScanner.from_env()
        assert scanner is not None
        assert str(scanner._start) == "10.0.0.1"
        assert str(scanner._end) == "10.0.0.100"


class TestArpScannerScan:
    def test_filters_entries_within_range(self):
        reader = _make_reader(
            ArpEntry(ip_address="192.168.1.200", mac_address="AA:BB:CC:DD:EE:01"),
            ArpEntry(ip_address="192.168.1.254", mac_address="AA:BB:CC:DD:EE:02"),
            ArpEntry(ip_address="192.168.1.100", mac_address="AA:BB:CC:DD:EE:03"),
        )
        scanner = ArpScanner("192.168.1.200", "192.168.1.254", arp_reader=reader)
        results = scanner.scan()
        assert len(results) == 2
        assert all(r.ip_address in ("192.168.1.200", "192.168.1.254") for r in results)

    def test_returns_empty_when_no_entries_in_range(self):
        reader = _make_reader(ArpEntry(ip_address="10.0.0.1", mac_address="AA:BB:CC:DD:EE:01"))
        scanner = ArpScanner("192.168.1.200", "192.168.1.254", arp_reader=reader)
        assert scanner.scan() == []

    def test_returns_empty_when_no_entries(self):
        scanner = ArpScanner("192.168.1.200", "192.168.1.254", arp_reader=lambda: [])
        assert scanner.scan() == []

    def test_includes_boundary_ips(self):
        reader = _make_reader(
            ArpEntry(ip_address="192.168.1.200", mac_address="AA:BB:CC:DD:EE:01"),
            ArpEntry(ip_address="192.168.1.254", mac_address="AA:BB:CC:DD:EE:02"),
        )
        scanner = ArpScanner("192.168.1.200", "192.168.1.254", arp_reader=reader)
        assert len(scanner.scan()) == 2
