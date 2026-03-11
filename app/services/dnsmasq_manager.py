from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv
from app.utils.write_devices import DnsmasqConfigWriter

load_dotenv(override=True)

CommandRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class DnsmasqCommandError(RuntimeError):
	command: Sequence[str]


def _default_command_runner(command: Sequence[str]) -> None:
	subprocess.run(list(command), check=True)


class DnsmasqManager:
	@classmethod
	def from_env(cls) -> "DnsmasqManager | None":
		conf_path = os.getenv("DNSMASQ_DHCP_CONF_PATH")
		if not conf_path:
			return None

		service_name = os.getenv("DNSMASQ_SERVICE_NAME", "dnsmasq")
		systemctl_path = os.getenv("DNSMASQ_SYSTEMCTL_PATH", "systemctl")
		return cls(
			dhcp_conf_path=Path(conf_path),
			service_name=service_name,
			systemctl_path=systemctl_path,
		)

	def __init__(
		self,
		*,
		dhcp_conf_path: Path,
		command_runner: CommandRunner | None = None,
		service_name: str = "dnsmasq",
		systemctl_path: str = "systemctl",
	) -> None:
		self._dhcp_conf_path = dhcp_conf_path
		self._run = command_runner or _default_command_runner
		self._service_name = service_name
		self._systemctl_path = systemctl_path

	def stop(self) -> None:
		self._run_command([self._systemctl_path, "stop", self._service_name])

	def start(self) -> None:
		self._run_command([self._systemctl_path, "start", self._service_name])

	def restart(self) -> None:
		self._run_command([self._systemctl_path, "restart", self._service_name])

	def write_dhcp_conf(self, devices: Sequence[dict[str, str]]) -> None:
		writer = DnsmasqConfigWriter()
		writer.write_config(devices, self._dhcp_conf_path)

	def apply(self, devices: Sequence[dict[str, str]]) -> None:
		"""Stop dnsmasq, write dhcp.conf, then start dnsmasq.

		Designed to be safe to call on a dev machine where dnsmasq may not be
		installed: tests inject a fake command runner.
		"""

		self.stop()
		try:
			self.write_dhcp_conf(devices)
		except Exception:
			# Best-effort recovery: if we stopped dnsmasq, try to bring it back.
			try:
				self.start()
			except Exception:
				pass
			raise
		self.start()

	def _run_command(self, command: Sequence[str]) -> None:
		try:
			self._run(command)
		except subprocess.CalledProcessError as exc:
			raise DnsmasqCommandError(command=command) from exc
