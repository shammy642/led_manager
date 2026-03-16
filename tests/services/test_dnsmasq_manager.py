from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from unittest.mock import MagicMock, patch

from app.services.dnsmasq_manager import DnsmasqCommandError, DnsmasqManager, DnsmasqStatus


class _Runner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.fail_on: tuple[str, ...] | None = None

    def __call__(self, command):
        cmd = list(command)
        self.commands.append(cmd)
        if self.fail_on is not None and tuple(cmd) == self.fail_on:
            raise subprocess.CalledProcessError(1, cmd)


def test_stop_start_restart_run_expected_systemctl_commands(tmp_path: Path):
    runner = _Runner()
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf", command_runner=runner)

    manager.stop()
    manager.start()
    manager.restart()

    assert runner.commands == [
        ["systemctl", "stop", "dnsmasq"],
        ["systemctl", "start", "dnsmasq"],
        ["systemctl", "restart", "dnsmasq"],
    ]


def test_write_dhcp_conf_delegates_to_writer(tmp_path: Path):
    runner = _Runner()
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path, command_runner=runner)

    manager.write_dhcp_conf(
        [
            {"name": "A", "ip_address": "10.0.0.1", "mac_address": "AA:BB:CC:DD:EE:FF"},
            {"name": "B", "ip_address": "10.0.0.2", "mac_address": "11:22:33:44:55:66"},
        ]
    )

    content = conf_path.read_text(encoding="utf-8")
    assert "dhcp-host=AA:BB:CC:DD:EE:FF,10.0.0.1,a" in content
    assert "dhcp-host=11:22:33:44:55:66,10.0.0.2,b" in content
    assert "interface=eth0" in content


def test_apply_stops_writes_starts(tmp_path: Path):
    runner = _Runner()
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path, command_runner=runner)

    manager.apply([{"name": "A", "ip_address": "10.0.0.1", "mac_address": "AA:BB:CC:DD:EE:FF"}])

    assert runner.commands == [
        ["systemctl", "stop", "dnsmasq"],
        ["systemctl", "start", "dnsmasq"],
    ]
    assert "dhcp-host=AA:BB:CC:DD:EE:FF,10.0.0.1,a" in conf_path.read_text(encoding="utf-8")


def test_apply_raises_if_stop_fails(tmp_path: Path):
    runner = _Runner()
    runner.fail_on = ("systemctl", "stop", "dnsmasq")
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf", command_runner=runner)

    with pytest.raises(DnsmasqCommandError) as exc_info:
        manager.apply([])

    assert list(exc_info.value.command) == ["systemctl", "stop", "dnsmasq"]


def test_apply_best_effort_starts_if_write_fails(tmp_path: Path):
    runner = _Runner()
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path, command_runner=runner)

    def _boom(_devices):
        raise ValueError("write failed")

    # Force write failure.
    manager.write_dhcp_conf = _boom  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="write failed"):
        manager.apply([])

    # Stop then best-effort start.
    assert runner.commands == [
        ["systemctl", "stop", "dnsmasq"],
        ["systemctl", "start", "dnsmasq"],
    ]


def test_get_status_returns_running_when_returncode_zero(tmp_path: Path):
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf")
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Active: active (running)"
        mock_run.return_value = mock_result

        status = manager.get_status()

    assert status.running is True
    assert status.status_text == "Active: active (running)"
    mock_run.assert_called_once_with(
        ["systemctl", "status", "dnsmasq"], capture_output=True, text=True
    )


def test_get_status_returns_not_running_with_nonzero_returncode(tmp_path: Path):
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf")
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 3
        mock_result.stdout = "Active: inactive (dead)"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        status = manager.get_status()

    assert status.running is False
    assert status.status_text == "Active: inactive (dead)"


def test_get_status_falls_back_to_stderr_when_stdout_empty(tmp_path: Path):
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf")
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 4
        mock_result.stdout = ""
        mock_result.stderr = "Unit dnsmasq.service could not be found."
        mock_run.return_value = mock_result

        status = manager.get_status()

    assert status.running is False
    assert status.status_text == "Unit dnsmasq.service could not be found."


def test_get_status_returns_error_text_on_exception(tmp_path: Path):
    manager = DnsmasqManager(dhcp_conf_path=tmp_path / "dhcp.conf")
    with patch("subprocess.run", side_effect=Exception("command not found")):
        status = manager.get_status()

    assert status.running is False
    assert status.status_text == "command not found"


def test_get_status_uses_configured_service_name(tmp_path: Path):
    manager = DnsmasqManager(
        dhcp_conf_path=tmp_path / "dhcp.conf",
        service_name="custom-dnsmasq",
        systemctl_path="/bin/systemctl",
    )
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "running"
        mock_run.return_value = mock_result

        manager.get_status()

    mock_run.assert_called_once_with(
        ["/bin/systemctl", "status", "custom-dnsmasq"], capture_output=True, text=True
    )


def test_write_dhcp_conf_includes_lease_file(tmp_path: Path):
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(
        dhcp_conf_path=conf_path,
        dhcp_lease_file="/var/lib/misc/dnsmasq.leases",
    )

    manager.write_dhcp_conf([])

    assert "dhcp-leasefile=/var/lib/misc/dnsmasq.leases" in conf_path.read_text(encoding="utf-8")


def test_write_dhcp_conf_no_lease_file_by_default(tmp_path: Path):
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path)

    manager.write_dhcp_conf([])

    assert "dhcp-leasefile" not in conf_path.read_text(encoding="utf-8")


def test_from_env_returns_none_when_no_conf_path(monkeypatch):
    monkeypatch.delenv("DNSMASQ_DHCP_CONF_PATH", raising=False)
    assert DnsmasqManager.from_env() is None


def test_from_env_sets_lease_file(tmp_path, monkeypatch):
    conf_path = str(tmp_path / "dhcp.conf")
    monkeypatch.setenv("DNSMASQ_DHCP_CONF_PATH", conf_path)
    monkeypatch.setenv("DNSMASQ_LEASE_FILE", "/tmp/dnsmasq.leases")
    monkeypatch.delenv("DNSMASQ_SERVICE_NAME", raising=False)
    monkeypatch.delenv("DNSMASQ_SYSTEMCTL_PATH", raising=False)

    manager = DnsmasqManager.from_env()
    assert manager is not None
    assert manager._dhcp_lease_file == "/tmp/dnsmasq.leases"


def test_from_env_lease_file_defaults_to_none(tmp_path, monkeypatch):
    conf_path = str(tmp_path / "dhcp.conf")
    monkeypatch.setenv("DNSMASQ_DHCP_CONF_PATH", conf_path)
    monkeypatch.delenv("DNSMASQ_LEASE_FILE", raising=False)

    manager = DnsmasqManager.from_env()
    assert manager is not None
    assert manager._dhcp_lease_file is None


def test_write_dhcp_conf_includes_default_address(tmp_path: Path):
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path)

    manager.write_dhcp_conf([])

    assert "address=/box9pi.box9/192.168.1.1" in conf_path.read_text(encoding="utf-8")


def test_write_dhcp_conf_excludes_address_when_none(tmp_path: Path):
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path, address=None)

    manager.write_dhcp_conf([])

    assert "address=" not in conf_path.read_text(encoding="utf-8")


def test_from_env_sets_address(tmp_path, monkeypatch):
    conf_path = str(tmp_path / "dhcp.conf")
    monkeypatch.setenv("DNSMASQ_DHCP_CONF_PATH", conf_path)
    monkeypatch.setenv("DNSMASQ_ADDRESS", "/myhost.lan/10.1.1.1")

    manager = DnsmasqManager.from_env()
    assert manager is not None
    assert manager._address == "/myhost.lan/10.1.1.1"


def test_from_env_omits_address_when_empty_string(tmp_path, monkeypatch):
    conf_path = str(tmp_path / "dhcp.conf")
    monkeypatch.setenv("DNSMASQ_DHCP_CONF_PATH", conf_path)
    monkeypatch.setenv("DNSMASQ_ADDRESS", "")

    manager = DnsmasqManager.from_env()
    assert manager is not None
    assert manager._address is None


def test_from_env_address_defaults_to_box9pi(tmp_path, monkeypatch):
    conf_path = str(tmp_path / "dhcp.conf")
    monkeypatch.setenv("DNSMASQ_DHCP_CONF_PATH", conf_path)
    monkeypatch.delenv("DNSMASQ_ADDRESS", raising=False)

    manager = DnsmasqManager.from_env()
    assert manager is not None
    assert manager._address == "/box9pi.box9/192.168.1.1"
