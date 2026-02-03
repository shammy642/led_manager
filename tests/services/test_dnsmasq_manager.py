from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.dnsmasq_manager import DnsmasqCommandError, DnsmasqManager


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

    assert conf_path.read_text(encoding="utf-8") == (
        "A,10.0.0.1,AA:BB:CC:DD:EE:FF\nB,10.0.0.2,11:22:33:44:55:66"
    )


def test_apply_stops_writes_starts(tmp_path: Path):
    runner = _Runner()
    conf_path = tmp_path / "dhcp.conf"
    manager = DnsmasqManager(dhcp_conf_path=conf_path, command_runner=runner)

    manager.apply([{"name": "A", "ip_address": "10.0.0.1", "mac_address": "AA:BB:CC:DD:EE:FF"}])

    assert runner.commands == [
        ["systemctl", "stop", "dnsmasq"],
        ["systemctl", "start", "dnsmasq"],
    ]
    assert "A,10.0.0.1,AA:BB:CC:DD:EE:FF" in conf_path.read_text(encoding="utf-8")


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
