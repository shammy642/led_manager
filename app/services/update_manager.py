from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

OutputCommandRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class UpdateStepResult:
    step: str
    success: bool
    output: str


@dataclass
class UpdateResult:
    success: bool
    steps: list[UpdateStepResult] = field(default_factory=list)


def _default_command_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
    )


class UpdateManager:
    @classmethod
    def from_env(cls) -> "UpdateManager":
        raw_rescan = os.getenv("UPDATE_RESCAN_WAIT_SECONDS", "5.0")
        try:
            rescan_wait_seconds = float(raw_rescan)
        except ValueError:
            rescan_wait_seconds = 5.0
        raw_wifi_on = os.getenv("UPDATE_WIFI_ON_WAIT_SECONDS", "3.0")
        try:
            wifi_on_wait_seconds = float(raw_wifi_on)
        except ValueError:
            wifi_on_wait_seconds = 3.0
        return cls(
            nmcli_path=os.getenv("UPDATE_NMCLI_PATH", "nmcli"),
            git_path=os.getenv("UPDATE_GIT_PATH", "git"),
            repo_path=Path(os.getenv("UPDATE_REPO_PATH", str(Path.cwd()))),
            service_name=os.getenv("UPDATE_SERVICE_NAME", ""),
            systemctl_path=os.getenv("UPDATE_SYSTEMCTL_PATH", "systemctl"),
            rescan_wait_seconds=rescan_wait_seconds,
            wifi_on_wait_seconds=wifi_on_wait_seconds,
        )

    def __init__(
        self,
        *,
        nmcli_path: str = "nmcli",
        git_path: str = "git",
        repo_path: Path | None = None,
        service_name: str = "",
        systemctl_path: str = "systemctl",
        rescan_wait_seconds: float = 5.0,
        wifi_on_wait_seconds: float = 3.0,
        command_runner: OutputCommandRunner | None = None,
    ) -> None:
        self._nmcli_path = nmcli_path
        self._git_path = git_path
        self._repo_path = repo_path or Path.cwd()
        self._service_name = service_name
        self._systemctl_path = systemctl_path
        self._rescan_wait_seconds = rescan_wait_seconds
        self._wifi_on_wait_seconds = wifi_on_wait_seconds
        self._run = command_runner or _default_command_runner

    def _run_step(self, step: str, command: Sequence[str]) -> UpdateStepResult:
        try:
            result = self._run(command)
            output = (result.stdout or "") + (result.stderr or "")
            return UpdateStepResult(step=step, success=result.returncode == 0, output=output.strip())
        except Exception as exc:
            return UpdateStepResult(step=step, success=False, output=str(exc))

    def enable_wifi(self) -> UpdateStepResult:
        result = self._run_step("wifi_on", [self._nmcli_path, "radio", "wifi", "on"])
        if result.success:
            time.sleep(self._wifi_on_wait_seconds)
        return result

    def rescan_wifi(self) -> UpdateStepResult:
        result = self._run_step("wifi_rescan", [self._nmcli_path, "dev", "wifi", "rescan"])
        if result.success:
            time.sleep(self._rescan_wait_seconds)
        return result

    def connect_wifi(self, ssid: str, password: str) -> UpdateStepResult:
        # Remove any pre-existing incomplete profile for this SSID — a stale
        # profile causes "key-mgmt: property is missing" on reconnect.
        self._run([self._nmcli_path, "connection", "delete", ssid])
        return self._run_step(
            "wifi_connect",
            [self._nmcli_path, "dev", "wifi", "connect", ssid, "password", password],
        )

    def git_pull(self) -> UpdateStepResult:
        return self._run_step(
            "git_pull",
            [self._git_path, "-C", str(self._repo_path), "pull"],
        )

    def disable_wifi(self) -> UpdateStepResult:
        return self._run_step("wifi_off", [self._nmcli_path, "radio", "wifi", "off"])

    def restart_service(self, delay_seconds: float = 2.0) -> None:
        if not self._service_name:
            return
        time.sleep(delay_seconds)
        subprocess.run(
            [self._systemctl_path, "restart", self._service_name],
            check=False,
        )

    def run_update(self, ssid: str, password: str) -> UpdateResult:
        steps: list[UpdateStepResult] = []

        wifi_on = self.enable_wifi()
        steps.append(wifi_on)
        if not wifi_on.success:
            return UpdateResult(success=False, steps=steps)

        rescan = self.rescan_wifi()
        steps.append(rescan)
        if not rescan.success:
            steps.append(self.disable_wifi())
            return UpdateResult(success=False, steps=steps)

        connect = self.connect_wifi(ssid, password)
        steps.append(connect)
        if not connect.success:
            steps.append(self.disable_wifi())
            return UpdateResult(success=False, steps=steps)

        pull = self.git_pull()
        steps.append(pull)
        if not pull.success:
            steps.append(self.disable_wifi())
            return UpdateResult(success=False, steps=steps)

        wifi_off = self.disable_wifi()
        steps.append(wifi_off)

        return UpdateResult(success=wifi_off.success, steps=steps)
