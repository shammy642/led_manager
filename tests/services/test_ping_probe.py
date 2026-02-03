import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.services.ping_probe import SubprocessIcmpPingProbe


class _FakeProc:
	def __init__(self, *, output: bytes, communicate_delay: float = 0.0):
		self._output = output
		self._delay = communicate_delay
		self.killed = False

	async def communicate(self):
		try:
			if self._delay:
				await asyncio.sleep(self._delay)
		except asyncio.CancelledError:
			raise
		return (self._output, None)

	def kill(self):
		self.killed = True


def test_parse_rtt_windows_time_less_than_one(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "win32")
	assert probe._parse_rtt_ms("Reply from 1.2.3.4: time<1ms") == 1.0


def test_parse_rtt_posix(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "linux")
	assert probe._parse_rtt_ms("64 bytes from 1.2.3.4: time=12.34 ms") == 12.34


def test_build_command_windows(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "win32")
	cmd = probe._build_command("10.0.0.1", timeout_seconds=1.25)
	assert cmd[:4] == ["ping", "-n", "1", "-w"]


def test_ping_once_success(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "linux")

	fake_proc = _FakeProc(output=b"64 bytes from 1.2.3.4: time=5.5 ms\n")

	async def _fake_create(*args, **kwargs):  # noqa: ARG001
		return fake_proc

	monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create)

	result = asyncio.run(probe.ping_once("1.2.3.4", timeout_seconds=0.2))
	assert result == 5.5
	assert fake_proc.killed is False


def test_ping_once_timeout_kills_process(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "linux")

	fake_proc = _FakeProc(output=b"", communicate_delay=10.0)

	async def _fake_create(*args, **kwargs):  # noqa: ARG001
		return fake_proc

	monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create)

	result = asyncio.run(probe.ping_once("1.2.3.4", timeout_seconds=0.01))
	assert result is None
	assert fake_proc.killed is True


def test_ping_once_cancelled_kills_process(monkeypatch):
	probe = SubprocessIcmpPingProbe()
	monkeypatch.setattr(sys, "platform", "linux")

	fake_proc = _FakeProc(output=b"", communicate_delay=10.0)

	async def _fake_create(*args, **kwargs):  # noqa: ARG001
		return fake_proc

	monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create)

	async def _run_cancel():
		task = asyncio.create_task(probe.ping_once("1.2.3.4", timeout_seconds=1.0))
		await asyncio.sleep(0)
		task.cancel()
		with pytest.raises(asyncio.CancelledError):
			await task

	asyncio.run(_run_cancel())
	assert fake_proc.killed is True
